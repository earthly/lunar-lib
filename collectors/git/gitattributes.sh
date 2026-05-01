#!/bin/bash
set -e

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_GITATTRIBUTES_PATHS"

CONFIG_FILE=""
for candidate in "${CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CONFIG_FILE="./$candidate"
    break
  fi
done

if [ -z "$CONFIG_FILE" ]; then
  exit 0
fi

PATH_NORMALIZED="${CONFIG_FILE#./}"

# Parse rules: skip blank lines and comments, split each rule into
# pattern + remaining attributes. .gitattributes is whitespace-separated
# with `pattern attr1 attr2=value ...`.
RULES_JSON=$(awk '
  /^[[:space:]]*(#|$)/ { next }
  {
    line = $0
    sub(/^[[:space:]]+/, "", line)
    sub(/[[:space:]]+$/, "", line)
    if (length(line) == 0) next
    n = split(line, fields, /[[:space:]]+/)
    pattern = fields[1]
    attrs = ""
    for (i = 2; i <= n; i++) {
      attrs = attrs (attrs == "" ? "" : " ") fields[i]
    }
    gsub(/"/, "\\\"", pattern)
    gsub(/"/, "\\\"", attrs)
    printf "{\"pattern\":\"%s\",\"attrs\":\"%s\"}\n", pattern, attrs
  }
' "$CONFIG_FILE" | jq -s '.' 2>/dev/null || echo "[]")

if [ -z "$RULES_JSON" ] || [ "$RULES_JSON" = "null" ]; then
  jq -n --arg path "$PATH_NORMALIZED" \
    '{valid: false, path: $path}' \
    | lunar collect -j ".git.attributes" -
  exit 0
fi

RULES_COUNT=$(echo "$RULES_JSON" | jq 'length')

LFS_PATTERNS=$(echo "$RULES_JSON" | jq -c '
  [.[] | select(.attrs | test("(^|[[:space:]])filter=lfs([[:space:]]|$)")) | .pattern]
')

BINARY_PATTERNS=$(echo "$RULES_JSON" | jq -c '
  [.[] | select(.attrs | test("(^|[[:space:]])binary([[:space:]]|$)")) | .pattern]
')

EXPORT_IGNORE_PATTERNS=$(echo "$RULES_JSON" | jq -c '
  [.[] | select(.attrs | test("(^|[[:space:]])export-ignore([[:space:]]|$)")) | .pattern]
')

# EOL normalization: any rule containing `text=auto`, bare `text`, or
# `eol=` qualifies. Pattern `*` covering all files is the canonical case
# but project-specific patterns also count.
EOL_NORMALIZED=$(echo "$RULES_JSON" | jq '
  any(.[]; .attrs | test("(^|[[:space:]])(text(=auto|=true)?|eol=(lf|crlf))([[:space:]]|$)"))
')

jq -n \
  --arg path "$PATH_NORMALIZED" \
  --argjson rules_count "$RULES_COUNT" \
  --argjson lfs_patterns "$LFS_PATTERNS" \
  --argjson binary_patterns "$BINARY_PATTERNS" \
  --argjson export_ignore_patterns "$EXPORT_IGNORE_PATTERNS" \
  --argjson eol_normalized "$EOL_NORMALIZED" \
  '{
    valid: true,
    path: $path,
    rules_count: $rules_count,
    lfs_patterns: $lfs_patterns,
    binary_patterns: $binary_patterns,
    eol_normalized: $eol_normalized,
    export_ignore_patterns: $export_ignore_patterns
  }' | lunar collect -j ".git.attributes" -
