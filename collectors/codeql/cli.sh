#!/bin/bash
set -e

# CI collector - runs native on CI runner

if [ -z "$LUNAR_CI_COMMAND" ]; then
    exit 0
fi

CMD_RAW="$LUNAR_CI_COMMAND"

if [[ "$CMD_RAW" == "["* ]]; then
    CMD_STR=$(echo "$CMD_RAW" | sed 's/^\[//; s/\]$//; s/","/ /g; s/"//g')
else
    CMD_STR="$CMD_RAW"
fi

if echo "$CMD_STR" | grep -qE '^(/usr/bin/)?git\s'; then
    exit 0
fi

if ! echo "$CMD_STR" | grep -qE '(^|/)(codeql|codeql-runner)(\s|$)'; then
    exit 0
fi

CODEQL_BIN="${LUNAR_CI_COMMAND_BIN_DIR:+$LUNAR_CI_COMMAND_BIN_DIR/}${LUNAR_CI_COMMAND_BIN:-codeql}"
CODEQL_VERSION=$("$CODEQL_BIN" version --format=terse 2>/dev/null || "$CODEQL_BIN" --version 2>/dev/null || echo "unknown")

CMD_SAFE=$(echo "$CMD_STR" | sed -E \
    -e 's/(--github-auth-stdin|--github-auth|--token)(=| )[^ ]+/\1=<redacted>/Ig')

CMD_ESCAPED=$(echo "$CMD_SAFE" | sed 's/"/\\"/g')

echo "{\"cmds\":[{\"cmd\":\"$CMD_ESCAPED\",\"version\":\"$CODEQL_VERSION\"}]}" | \
    lunar collect -j ".sast.native.codeql.cicd" -

lunar collect ".sast.source.tool" "codeql"
lunar collect ".sast.source.integration" "ci"
if [ -n "$CODEQL_VERSION" ] && [ "$CODEQL_VERSION" != "unknown" ]; then
    lunar collect ".sast.source.version" "$CODEQL_VERSION"
fi

# --- SARIF collection ---
# Only collect SARIF from commands that produce it:
#   codeql database interpret-results --output=<path>
#   codeql database analyze --output=<path>
if ! echo "$CMD_STR" | grep -qE 'database\s+(interpret-results|analyze)'; then
    exit 0
fi

# Parse --output=<path> from the command args
SARIF_PATH=""
if echo "$CMD_STR" | grep -qoE '\-\-output[= ]\S+'; then
    SARIF_PATH=$(echo "$CMD_STR" | grep -oE '\-\-output[= ]\S+' | head -1 | sed -E 's/--output[= ]//')
fi

if [ -z "$SARIF_PATH" ]; then
    exit 0
fi

# Resolve the SARIF file — try as-is first, then relative to $GITHUB_WORKSPACE
SARIF_FILE=""
if [ -f "$SARIF_PATH" ]; then
    SARIF_FILE="$SARIF_PATH"
elif [ -n "$GITHUB_WORKSPACE" ] && [ -f "$GITHUB_WORKSPACE/$SARIF_PATH" ]; then
    SARIF_FILE="$GITHUB_WORKSPACE/$SARIF_PATH"
elif [ -n "$GITHUB_WORKSPACE" ] && [ -f "$GITHUB_WORKSPACE/../results/$(basename "$SARIF_PATH")" ]; then
    SARIF_FILE="$GITHUB_WORKSPACE/../results/$(basename "$SARIF_PATH")"
fi

if [ -z "$SARIF_FILE" ]; then
    echo "SARIF file not found at $SARIF_PATH" >&2
    exit 0
fi

echo "Collecting SARIF from $SARIF_FILE" >&2

# Collect the raw SARIF under native
cat "$SARIF_FILE" | lunar collect -j ".sast.native.codeql.sarif" - || {
    echo "Warning: Failed to collect raw SARIF from $SARIF_FILE" >&2
    exit 0
}

# Normalize findings if jq is available
if ! command -v jq &>/dev/null; then
    echo "jq not available — skipping SARIF normalization" >&2
    exit 0
fi

# Extract findings from SARIF: walk runs[].results[] and cross-reference
# rules from runs[].tool.driver.rules[] for severity info.
# SARIF security-severity is in rule.properties.security-severity (numeric string)
# or rule.defaultConfiguration.level (note/warning/error).
NORMALIZED=$(jq -c '
  [.runs[]? | 
    (.tool.driver.rules // []) as $rules |
    .results[]? |
    . as $result |
    ($rules | map(select(.id == $result.ruleId)) | first // {}) as $rule |
    ($rule.properties["security-severity"] // null) as $sec_sev |
    (
      if $sec_sev != null then
        ($sec_sev | tonumber) as $n |
        if $n >= 9.0 then "critical"
        elif $n >= 7.0 then "high"
        elif $n >= 4.0 then "medium"
        else "low" end
      elif $rule.defaultConfiguration.level == "error" then "high"
      elif $rule.defaultConfiguration.level == "warning" then "medium"
      else "low" end
    ) as $severity |
    {
      severity: $severity,
      rule: $result.ruleId,
      file: ($result.locations[0]?.physicalLocation?.artifactLocation?.uri // null),
      line: ($result.locations[0]?.physicalLocation?.region?.startLine // null),
      message: ($result.message.text // null)
    }
  ]
' "$SARIF_FILE" 2>/dev/null) || {
    echo "Warning: Failed to parse SARIF for normalization" >&2
    exit 0
}

if [ -z "$NORMALIZED" ] || [ "$NORMALIZED" = "[]" ] || [ "$NORMALIZED" = "null" ]; then
    echo "{\"critical\":0,\"high\":0,\"medium\":0,\"low\":0,\"total\":0}" | \
        lunar collect -j ".sast.findings" -
    echo "{\"has_critical\":false,\"has_high\":false}" | \
        lunar collect -j ".sast.summary" -
    lunar collect -j ".sast.issues" "[]"
    exit 0
fi

echo "$NORMALIZED" | lunar collect -j ".sast.issues" -

# Compute severity counts
COUNTS=$(echo "$NORMALIZED" | jq -c '
  group_by(.severity) | map({key: .[0].severity, value: length}) | from_entries |
  {
    critical: (.critical // 0),
    high: (.high // 0),
    medium: (.medium // 0),
    low: (.low // 0),
    total: length
  }
' 2>/dev/null) || COUNTS=""

if [ -n "$COUNTS" ] && [ "$COUNTS" != "null" ]; then
    TOTAL=$(echo "$NORMALIZED" | jq 'length')
    COUNTS=$(echo "$COUNTS" | jq --argjson total "$TOTAL" '.total = $total')
    echo "$COUNTS" | lunar collect -j ".sast.findings" -

    HAS_CRITICAL=$(echo "$COUNTS" | jq '.critical > 0')
    HAS_HIGH=$(echo "$COUNTS" | jq '.high > 0')
    echo "{\"has_critical\":$HAS_CRITICAL,\"has_high\":$HAS_HIGH}" | \
        lunar collect -j ".sast.summary" -
fi
