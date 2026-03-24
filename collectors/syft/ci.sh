#!/bin/bash
set -e

CMD_RAW="$LUNAR_CI_COMMAND"

# Convert JSON array to plain command string for parsing
CMD=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
# Escaped version for safe JSON embedding
CMD_ESC=$(printf '%s' "$CMD" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get syft version using the exact traced binary
SYFT_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-syft}"
VERSION=$("$SYFT_BIN" version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' || echo "")

if [ -n "$VERSION" ]; then
  lunar collect -j ".sbom.native.syft.cicd.cmds" "[{\"cmd\":\"$CMD_ESC\",\"version\":\"$VERSION\"}]"
else
  lunar collect -j ".sbom.native.syft.cicd.cmds" "[{\"cmd\":\"$CMD_ESC\"}]"
fi

# Parse the command to find output file and format.
# All regex matching operates on $CMD (plain space-separated string),
# not $CMD_RAW (JSON array where elements are separated by "," not spaces).
OUTPUT_FILE=""
OUTPUT_FORMAT=""

# 1) -o cyclonedx-json=sbom.json, --output spdx-json@1.6=report.json
if echo "$CMD" | grep -qoE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?=\S+'; then
  MATCH=$(echo "$CMD" | grep -oE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?=\S+' | head -1)
  FORMAT_FILE=$(echo "$MATCH" | sed -E 's/(-o|--output)\s+//')
  OUTPUT_FORMAT=$(echo "$FORMAT_FILE" | cut -d'=' -f1 | sed 's/@.*//')
  OUTPUT_FILE=$(echo "$FORMAT_FILE" | cut -d'=' -f2)
fi

# 2) -o cyclonedx-json (no file — stdout)
if [ -z "$OUTPUT_FORMAT" ]; then
  if echo "$CMD" | grep -qoE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?(\s|$)'; then
    OUTPUT_FORMAT=$(echo "$CMD" | grep -oE '(-o|--output)\s+[a-z]+(-[a-z]+)?(@[0-9.]+)?' | head -1 | sed -E 's/(-o|--output)\s+//' | sed 's/@.*//')
  fi
fi

# 3) Deprecated --file flag (still used by some workflows)
if [ -z "$OUTPUT_FILE" ]; then
  if echo "$CMD" | grep -qoE '(--file)\s+\S+'; then
    OUTPUT_FILE=$(echo "$CMD" | grep -oE '(--file)\s+(\S+)' | head -1 | sed -E 's/--file\s+//')
  fi
fi

# 4) Shell redirect: syft ... > file.json
if [ -z "$OUTPUT_FILE" ]; then
  if echo "$CMD" | grep -qoE '>\s*\S+\.json'; then
    OUTPUT_FILE=$(echo "$CMD" | grep -oE '>\s*(\S+\.json)' | head -1 | sed 's/>\s*//')
  fi
fi

# 5) Fallback: when syft writes to stdout (no =file, no --file, no redirect), GH Actions
# like anchore-sbom-action capture stdout and write it to a temp file. Search for recently
# created SBOM files in known locations.
if [ -z "$OUTPUT_FILE" ] && [ -n "$OUTPUT_FORMAT" ]; then
  find_sbom_file() {
    local candidates=""
    for d in /tmp/sbom-action-*; do
      [ -d "$d" ] && candidates="$candidates $(ls -t "$d"/*.spdx "$d"/*.json "$d"/*.spdx.json "$d"/*.cyclonedx.json 2>/dev/null | head -3)"
    done
    for dir in "${GITHUB_WORKSPACE:-.}" "${RUNNER_TEMP:-}" "/tmp"; do
      [ -z "$dir" ] || [ ! -d "$dir" ] && continue
      for pattern in "sbom*.json" "*.sbom.json" "*.cyclonedx.json" "*.spdx.json"; do
        candidates="$candidates $(ls -t "$dir"/$pattern 2>/dev/null | head -3)"
      done
    done
    for f in $candidates; do
      [ -f "$f" ] || continue
      if head -c 2048 "$f" | grep -qE '"bomFormat"|"spdxVersion"|"BOMFormat"' 2>/dev/null; then
        echo "$f"
        return 0
      fi
    done
    return 1
  }
  OUTPUT_FILE=$(find_sbom_file 2>/dev/null) || true
  if [ -z "$OUTPUT_FILE" ]; then
    sleep 1
    OUTPUT_FILE=$(find_sbom_file 2>/dev/null) || true
  fi
  if [ -n "$OUTPUT_FILE" ]; then
    echo "Found SBOM file via fallback search: $OUTPUT_FILE" >&2
  fi
fi

# If we found a file but don't know the format, auto-detect from content.
if [ -z "$OUTPUT_FORMAT" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  if head -c 2048 "$OUTPUT_FILE" | grep -q '"bomFormat"' 2>/dev/null; then
    OUTPUT_FORMAT="cyclonedx-json"
  elif head -c 2048 "$OUTPUT_FILE" | grep -q '"spdxVersion"' 2>/dev/null; then
    OUTPUT_FORMAT="spdx-json"
  fi
fi

SBOM_PATH=""
case "$OUTPUT_FORMAT" in
  cyclonedx-json)
    SBOM_PATH=".sbom.cicd.cyclonedx"
    ;;
  spdx-json)
    SBOM_PATH=".sbom.cicd.spdx"
    ;;
  json)
    SBOM_PATH=".sbom.native.syft.cicd.raw"
    ;;
  github-json)
    SBOM_PATH=".sbom.native.syft.cicd.github"
    ;;
esac

if [ -n "$SBOM_PATH" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  echo "Collecting SBOM from $OUTPUT_FILE (format: $OUTPUT_FORMAT)" >&2
  cat "$OUTPUT_FILE" | lunar collect -j "$SBOM_PATH" - || \
    echo "Warning: Failed to collect SBOM from $OUTPUT_FILE" >&2
elif [ -n "$SBOM_PATH" ] && [ -z "$OUTPUT_FILE" ]; then
  echo "Syft wrote to stdout; no output file found to collect (format: $OUTPUT_FORMAT)" >&2
elif [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  echo "Skipping SBOM file collection: unknown format '$OUTPUT_FORMAT'" >&2
fi
