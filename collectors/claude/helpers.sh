#!/bin/bash

# Shared helpers for Claude CI collectors.
# These run native (no jq) — must use pure bash.

# Get tool version using the exact traced binary path.
get_tool_version() {
  local tool="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-$1}"
  "$tool" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+[.0-9]*' | head -1 || echo ""
}

# Parse LUNAR_CI_COMMAND JSON array into a space-separated string (no jq).
parse_cmd_str() {
  echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g'
}

# Escape a string for safe embedding in a JSON string value.
json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' ' '
}

# Extract a single flag value from a command string.
extract_flag_value() {
  local cmd="$1"
  shift
  for flag in "$@"; do
    local val
    val=$(awk -v f="$flag" '{
      for (i=1; i<=NF; i++) {
        if ($i == f && (i+1) <= NF) { print $(i+1); exit }
        if (index($i, f "=") == 1) { sub(f "=", "", $i); print $i; exit }
      }
    }' <<< "$cmd" 2>/dev/null || true)
    if [ -n "$val" ]; then
      echo "$val"
      return
    fi
  done
  echo ""
}

# Extract all values following a flag that accepts multiple space-separated args.
extract_flag_values() {
  local cmd="$1"
  local flag="$2"
  echo "$cmd" | sed -n "s/.*${flag} \(.*\)/\1/p" | sed 's/ --.*$//' | xargs 2>/dev/null || echo ""
}
