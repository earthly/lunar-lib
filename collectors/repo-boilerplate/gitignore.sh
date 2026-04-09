#!/bin/bash

set -e

if [ ! -f ".gitignore" ]; then
  lunar collect -j ".repo.gitignore.exists" false
  exit 0
fi

# Count total lines
LINES=$(wc -l < ".gitignore" | tr -d ' ')

# Count active patterns (non-empty, non-comment lines)
PATTERNS=$(grep -cve '^\s*$' -e '^\s*#' ".gitignore" 2>/dev/null || echo 0)

JSON=$(jq -n \
  --argjson exists true \
  --arg path ".gitignore" \
  --argjson lines "$LINES" \
  --argjson patterns "$PATTERNS" \
  '{
    exists: $exists,
    path: $path,
    lines: $lines,
    patterns: $patterns
  }')

echo "$JSON" | lunar collect -j ".repo.gitignore" -
