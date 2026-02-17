#!/bin/bash

# Shared helpers for AI CLI CI collectors.
# These run native (no jq) — must use pure bash.

# Get tool version by running "<tool> --version" and extracting first version-like string.
get_tool_version() {
  local tool="$1"
  "$tool" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+[.0-9]*' | head -1 || echo ""
}

# Parse LUNAR_CI_COMMAND JSON array into a space-separated string (no jq).
parse_cmd_str() {
  echo "$LUNAR_CI_COMMAND" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g'
}

# Extract a single flag value from a command string.
# Supports short and long forms: extract_flag_value "$cmd" "--sandbox" "-s"
# Returns the value after the flag, or empty if not found.
extract_flag_value() {
  local cmd="$1"
  shift
  for flag in "$@"; do
    # Match "--flag value" or "--flag=value"
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
# e.g., --allowedTools "Bash(git log *)" "Read" → returns the raw string of all args
# Captures everything between this flag and the next --flag or end of string.
extract_flag_values() {
  local cmd="$1"
  local flag="$2"
  # Get everything after the flag until the next --flag or end
  echo "$cmd" | sed -n "s/.*${flag} \(.*\)/\1/p" | sed 's/ --.*$//' | xargs 2>/dev/null || echo ""
}
