#!/bin/bash
set -e

CMD_RAW="$LUNAR_CI_COMMAND"

# Convert JSON array to plain command string for parsing
CMD=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
# Escaped version for safe JSON embedding
CMD_ESC=$(printf '%s' "$CMD" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Redact secrets from command
CMD_ESC=$(echo "$CMD_ESC" | sed -E \
  -e 's/(--bc-api-key|--api-key|--token)(=| )[^ ]+/\1=<redacted>/g' \
  -e 's/(CHECKOV_API_KEY|BC_API_KEY|PRISMA_API_KEY)=[^ ]+/\1=<redacted>/g')

# Get checkov version using the exact traced binary
CHECKOV_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-checkov}"
VERSION=$("$CHECKOV_BIN" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")

# Record command metadata
if [ -n "$VERSION" ]; then
  lunar collect -j ".iac_scan.native.checkov.cicd.cmds" "[{\"cmd\":\"$CMD_ESC\",\"version\":\"$VERSION\"}]"
  lunar collect ".iac_scan.source.tool" "checkov"
  lunar collect ".iac_scan.source.integration" "ci"
  lunar collect ".iac_scan.source.version" "$VERSION"
else
  lunar collect -j ".iac_scan.native.checkov.cicd.cmds" "[{\"cmd\":\"$CMD_ESC\"}]"
  lunar collect ".iac_scan.source.tool" "checkov"
  lunar collect ".iac_scan.source.integration" "ci"
fi

# Try to find the report file from --output-file-path flag
REPORT_DIR=""

# Pattern 1: --output-file-path <dir> or --output-file-path=<dir>
if echo "$CMD" | grep -qE '(--output-file-path)[= ]\S+'; then
  REPORT_DIR=$(echo "$CMD" | grep -oE '(--output-file-path)[= ](\S+)' | head -1 | sed -E 's/(--output-file-path)[= ]//')
fi

# Pattern 2: -o <dir> (short flag, but only if followed by a path-like string)
if [ -z "$REPORT_DIR" ]; then
  if echo "$CMD" | grep -qE '\s-o\s+/\S+'; then
    REPORT_DIR=$(echo "$CMD" | grep -oE '\s-o\s+(/\S+)' | head -1 | sed -E 's/\s+-o\s+//')
  fi
fi

# Checkov writes to <dir>/results_json.json when using --output json --output-file-path <dir>
REPORT_FILE=""
if [ -n "$REPORT_DIR" ]; then
  if [ -f "$REPORT_DIR/results_json.json" ]; then
    REPORT_FILE="$REPORT_DIR/results_json.json"
  elif [ -f "$REPORT_DIR" ]; then
    # User might have passed a file path directly
    REPORT_FILE="$REPORT_DIR"
  fi
fi

# Also check for shell redirect > file.json
if [ -z "$REPORT_FILE" ]; then
  if echo "$CMD" | grep -qE '>\s*\S+\.json'; then
    REDIRECT_FILE=$(echo "$CMD" | grep -oE '>\s*(\S+\.json)' | head -1 | sed 's/>\s*//')
    if [ -f "$REDIRECT_FILE" ]; then
      REPORT_FILE="$REDIRECT_FILE"
    fi
  fi
fi

# Collect and normalize the report if found
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ]; then
  echo "Collecting Checkov report from $REPORT_FILE" >&2

  # Validate JSON
  if ! jq empty "$REPORT_FILE" 2>/dev/null; then
    echo "Report file is not valid JSON, skipping" >&2
    exit 0
  fi

  # Parse findings using same logic as scan.sh
  jq '
    (if type == "array" then . else [.] end) as $frameworks |
    [$frameworks[] | .results.failed_checks[]?] as $failed |
    ($failed | map(select(.severity == "CRITICAL")) | length) as $critical |
    ($failed | map(select(.severity == "HIGH")) | length) as $high |
    ($failed | map(select(.severity == "MEDIUM")) | length) as $medium |
    ($failed | map(select(.severity == "LOW" or .severity == "INFO" or .severity == null or .severity == "UNKNOWN")) | length) as $low |
    ($failed | length) as $total |
    {
      findings: { critical: $critical, high: $high, medium: $medium, low: $low, total: $total },
      summary: { has_critical: ($critical > 0), has_high: ($high > 0), has_medium: ($medium > 0), has_low: ($low > 0) }
    }
  ' "$REPORT_FILE" > /tmp/checkov-cicd-parsed.json 2>/dev/null

  if [ -s /tmp/checkov-cicd-parsed.json ]; then
    jq '.findings' /tmp/checkov-cicd-parsed.json | lunar collect -j ".iac_scan.findings" - || \
      echo "Warning: Failed to collect findings" >&2
    jq '.summary' /tmp/checkov-cicd-parsed.json | lunar collect -j ".iac_scan.summary" - || \
      echo "Warning: Failed to collect summary" >&2
  fi
elif [ -n "$REPORT_DIR" ]; then
  echo "Report directory $REPORT_DIR found but no results_json.json inside" >&2
else
  echo "No --output-file-path flag found in command; skipping report collection" >&2
fi
