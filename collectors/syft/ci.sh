#!/bin/bash
set -e

CMD="$LUNAR_CI_COMMAND"

# Extract command string for cmds array
CMD_STR=$(echo "$CMD" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
CMD_STR=$(printf '%s' "$CMD_STR" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Try to get syft version (no jq — CI runners may not have it)
VERSION=""
if command -v syft &>/dev/null; then
  VERSION=$(syft version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")
fi

# Write tool-specific CI metadata under .sbom.native.syft.cicd
# This follows the .native.{tool}.cicd convention (matching Snyk, manifest-cyber)
if [ -n "$VERSION" ]; then
  lunar collect -j ".sbom.native.syft.cicd.cmds" "[{\"cmd\":\"$CMD_STR\",\"version\":\"$VERSION\"}]"
else
  lunar collect -j ".sbom.native.syft.cicd.cmds" "[{\"cmd\":\"$CMD_STR\"}]"
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

# Determine the SBOM format — only collect JSON formats we recognize
# SBOM content goes to normalized .sbom.cicd paths (tool-agnostic)
# Syft formats: json (native), cyclonedx-json, cyclonedx-xml, spdx-json, spdx-tag-value,
#               github-json, table, text, purls, template
SBOM_PATH=""
case "$OUTPUT_FORMAT" in
  cyclonedx-json)
    SBOM_PATH=".sbom.cicd.cyclonedx"
    ;;
  spdx-json)
    SBOM_PATH=".sbom.cicd.spdx"
    ;;
  json)
    # Syft native JSON format — tool-specific, goes under native
    SBOM_PATH=".sbom.native.syft.cicd.raw"
    ;;
  github-json)
    SBOM_PATH=".sbom.native.syft.cicd.github"
    ;;
  # XML and text formats (cyclonedx-xml, spdx-tag-value, table, text, purls, template)
  # are not collected — lunar collect requires JSON
esac

# If we found an output file AND know the format, collect it
if [ -n "$SBOM_PATH" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  echo "Collecting SBOM from $OUTPUT_FILE (format: $OUTPUT_FORMAT)" >&2
  cat "$OUTPUT_FILE" | lunar collect -j "$SBOM_PATH" - || \
    echo "Warning: Failed to collect SBOM from $OUTPUT_FILE" >&2
elif [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  echo "Skipping SBOM file collection: unknown format '$OUTPUT_FORMAT'" >&2
fi
