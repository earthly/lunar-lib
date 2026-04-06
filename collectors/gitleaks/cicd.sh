#!/bin/bash
set -e

CMD_RAW="$LUNAR_CI_COMMAND"

# Convert JSON array to plain command string for parsing
CMD=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
# Escaped version for safe JSON embedding
CMD_ESC=$(printf '%s' "$CMD" | sed 's/\\/\\\\/g; s/"/\\"/g')

# Get gitleaks version using the exact traced binary
GITLEAKS_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-gitleaks}"
VERSION=$("$GITLEAKS_BIN" version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1 || echo "")

# Record command metadata
if [ -n "$VERSION" ]; then
  lunar collect -j ".secrets.native.gitleaks.cicd.cmds" "[{\"cmd\":\"$CMD_ESC\",\"version\":\"$VERSION\"}]"
  lunar collect ".secrets.source.tool" "gitleaks"
  lunar collect ".secrets.source.integration" "ci"
  lunar collect ".secrets.source.version" "$VERSION"
else
  lunar collect -j ".secrets.native.gitleaks.cicd.cmds" "[{\"cmd\":\"$CMD_ESC\"}]"
  lunar collect ".secrets.source.tool" "gitleaks"
  lunar collect ".secrets.source.integration" "ci"
fi

# Try to find the report file from --report-path / -r flags
REPORT_FILE=""

# Pattern 1: --report-path <file> or --report-path=<file>
if echo "$CMD" | grep -qE '(--report-path)[= ]\S+'; then
  REPORT_FILE=$(echo "$CMD" | grep -oE '(--report-path)[= ](\S+)' | head -1 | sed -E 's/(--report-path)[= ]//')
fi

# Pattern 2: -r <file> (short flag)
if [ -z "$REPORT_FILE" ]; then
  if echo "$CMD" | grep -qE '\s-r\s+\S+'; then
    REPORT_FILE=$(echo "$CMD" | grep -oE '\s-r\s+(\S+)' | head -1 | sed -E 's/\s+-r\s+//')
  fi
fi

# Pattern 3: Shell redirect > file.json
if [ -z "$REPORT_FILE" ]; then
  if echo "$CMD" | grep -qE '>\s*\S+\.json'; then
    REPORT_FILE=$(echo "$CMD" | grep -oE '>\s*(\S+\.json)' | head -1 | sed 's/>\s*//')
  fi
fi

# Collect the report if found
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
  echo "Collecting gitleaks report from $REPORT_FILE" >&2

  # Collect raw report
  cat "$REPORT_FILE" | lunar collect -j ".secrets.native.gitleaks.cicd.report" - || \
    echo "Warning: Failed to collect raw report" >&2

  # Normalize findings into .secrets.cicd
  if jq -e 'type == "array"' "$REPORT_FILE" >/dev/null 2>&1; then
    jq '[.[] | {
      rule: .RuleID,
      file: .File,
      line: .StartLine,
      secret_type: .Description
    }]' "$REPORT_FILE" | lunar collect -j ".secrets.cicd" - || \
      echo "Warning: Failed to normalize report" >&2
  fi
elif [ -n "$REPORT_FILE" ]; then
  echo "Report file $REPORT_FILE not found" >&2
else
  echo "No --report-path or -r flag found in command; skipping report collection" >&2
fi
