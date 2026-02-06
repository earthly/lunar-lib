#!/bin/bash
set -e

CMD="$LUNAR_CI_COMMAND"

# Record source metadata - presence signals syft ran in CI
lunar collect ".sbom.cicd.source.tool" "syft"
lunar collect ".sbom.cicd.source.integration" "ci"

# Record CI artifact signal
lunar collect -j ".ci.artifacts.sbom_generated" true

# Try to get syft version
if command -v syft &>/dev/null; then
  VERSION=$(syft version -o json 2>/dev/null | jq -r '.version // empty' 2>/dev/null || \
    syft version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
  if [ -n "$VERSION" ]; then
    lunar collect ".sbom.cicd.source.version" "$VERSION"
  fi
fi

# Parse the command to find output file and format
# Syft output flags: -o/--output <format>=<file> or -o <format> with stdout
OUTPUT_FILE=""
OUTPUT_FORMAT=""

# Match patterns like: -o cyclonedx-json=sbom.json, --output spdx-json=report.json
if echo "$CMD" | grep -qoE '(-o|--output)\s+[a-z]+-[a-z]+=\S+'; then
  MATCH=$(echo "$CMD" | grep -oE '(-o|--output)\s+([a-z]+-[a-z]+=\S+)' | head -1)
  FORMAT_FILE=$(echo "$MATCH" | sed -E 's/(-o|--output)\s+//')
  OUTPUT_FORMAT=$(echo "$FORMAT_FILE" | cut -d'=' -f1)
  OUTPUT_FILE=$(echo "$FORMAT_FILE" | cut -d'=' -f2)
fi

# Match patterns like: -o cyclonedx-json (output to stdout, may be redirected)
if [ -z "$OUTPUT_FORMAT" ]; then
  if echo "$CMD" | grep -qoE '(-o|--output)\s+[a-z]+-[a-z]+'; then
    OUTPUT_FORMAT=$(echo "$CMD" | grep -oE '(-o|--output)\s+([a-z]+-[a-z]+)' | head -1 | sed -E 's/(-o|--output)\s+//')
  fi
fi

# Try to detect redirect: syft ... > file.json
if [ -z "$OUTPUT_FILE" ]; then
  if echo "$CMD" | grep -qoE '>\s*\S+\.json'; then
    OUTPUT_FILE=$(echo "$CMD" | grep -oE '>\s*(\S+\.json)' | head -1 | sed 's/>\s*//')
  fi
fi

# Determine the SBOM format category
SBOM_PATH=""
case "$OUTPUT_FORMAT" in
  cyclonedx-json|cyclonedx*)
    SBOM_PATH=".sbom.cicd.cyclonedx"
    ;;
  spdx-json|spdx*)
    SBOM_PATH=".sbom.cicd.spdx"
    ;;
  *)
    # Default to cyclonedx if format unclear
    SBOM_PATH=".sbom.cicd.cyclonedx"
    ;;
esac

# If we found an output file, collect it
if [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  # Verify it's valid JSON before collecting
  if jq empty "$OUTPUT_FILE" 2>/dev/null; then
    echo "Collecting SBOM from $OUTPUT_FILE" >&2
    cat "$OUTPUT_FILE" | lunar collect -j "$SBOM_PATH" -
  else
    echo "Warning: SBOM output file $OUTPUT_FILE is not valid JSON" >&2
  fi
fi
