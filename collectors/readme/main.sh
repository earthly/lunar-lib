#!/bin/bash

set -e

# Convert comma-separated paths input to array
IFS=',' read -ra README_CANDIDATES <<< "$LUNAR_VAR_PATH"

# Find the first matching README file
README_FILE=""
for candidate in "${README_CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    README_FILE="./$candidate"
    break
  fi
done

# No README file found
if [ -z "$README_FILE" ]; then
  lunar collect -j ".repo.readme.exists" false
  exit 0
fi

# Normalize path (remove leading ./)
PATH_NORMALIZED="${README_FILE#./}"

# Count lines
LINES=$(wc -l < "$README_FILE" | tr -d ' ')

# Extract sections (headers starting with #, ##, ###, etc.)
# Remove the # symbols, strip markdown links/badges (everything from [ onwards), and trim whitespace
SECTIONS=$(grep -E '^#{1,6}\s+' "$README_FILE" 2>/dev/null | sed 's/^#\{1,6\}\s*//' | sed 's/\s*\[.*$//' | sed 's/^\s*//;s/\s*$//' | jq -R . | jq -s . || echo '[]')

# Build JSON object
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

echo "$JSON" | lunar collect -j ".repo.readme" -
