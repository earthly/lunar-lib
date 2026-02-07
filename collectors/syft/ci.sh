#!/bin/bash
set -e

CMD="$LUNAR_CI_COMMAND"

# Record source metadata - presence signals syft ran in CI
lunar collect ".sbom.cicd.source.tool" "syft"
lunar collect ".sbom.cicd.source.integration" "ci"

# Try to get syft version (no jq — CI runners may not have it)
if command -v syft &>/dev/null; then
  VERSION=$(syft version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
  if [ -n "$VERSION" ]; then
    lunar collect ".sbom.cicd.source.version" "$VERSION"
  fi
fi

# Parse the command to find output file and format
# Syft output flags: -o/--output <format>=<file> or -o <format> with stdout
OUTPUT_FILE=""
OUTPUT_FORMAT=""

# Match patterns like: -o cyclonedx-json=sbom.json, --output spdx-json@1.6=report.json
# Supports: simple (json), hyphenated (cyclonedx-json), versioned (cyclonedx-json@1.6)
if echo "$CMD" | grep -qoE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?=\S+'; then
  MATCH=$(echo "$CMD" | grep -oE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?=\S+' | head -1)
  FORMAT_FILE=$(echo "$MATCH" | sed -E 's/(-o|--output)\s+//')
  OUTPUT_FORMAT=$(echo "$FORMAT_FILE" | cut -d'=' -f1 | sed 's/@.*//')
  OUTPUT_FILE=$(echo "$FORMAT_FILE" | cut -d'=' -f2)
fi

# Match patterns like: -o cyclonedx-json, -o json, -o spdx-json@2.3
if [ -z "$OUTPUT_FORMAT" ]; then
  if echo "$CMD" | grep -qoE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?(\s|$)'; then
    OUTPUT_FORMAT=$(echo "$CMD" | grep -oE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?' | head -1 | sed -E 's/(-o|--output)\s+//' | sed 's/@.*//')
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

# If we found an output file, collect it (lunar collect -j validates JSON internally)
if [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  echo "Collecting SBOM from $OUTPUT_FILE" >&2
  cat "$OUTPUT_FILE" | lunar collect -j "$SBOM_PATH" - || \
    echo "Warning: Failed to collect SBOM from $OUTPUT_FILE" >&2
fi
