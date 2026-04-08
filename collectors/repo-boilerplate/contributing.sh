#!/bin/bash

set -e

# Check root and .github/ locations
CONTRIBUTING_FILE=""
for candidate in CONTRIBUTING.md .github/CONTRIBUTING.md; do
  if [ -f "./$candidate" ]; then
    CONTRIBUTING_FILE="./$candidate"
    break
  fi
done

if [ -z "$CONTRIBUTING_FILE" ]; then
  lunar collect -j ".repo.contributing.exists" false
  exit 0
fi

PATH_NORMALIZED="${CONTRIBUTING_FILE#./}"

# Count lines
LINES=$(wc -l < "$CONTRIBUTING_FILE" | tr -d ' ')

# Extract sections
SECTIONS=$(grep -E '^#{1,6}\s+' "$CONTRIBUTING_FILE" 2>/dev/null | sed 's/^#\{1,6\}\s*//' | sed 's/\s*\[.*$//' | sed 's/^\s*//;s/\s*$//' | jq -R . | jq -s . || echo '[]')

JSON=$(jq -n \
  --argjson exists true \
  --arg path "$PATH_NORMALIZED" \
  --argjson lines "$LINES" \
  --argjson sections "$SECTIONS" \
  '{
    exists: $exists,
    path: $path,
    lines: $lines,
    sections: $sections
  }')

echo "$JSON" | lunar collect -j ".repo.contributing" -
