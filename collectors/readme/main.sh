#!/bin/bash

set -e

# Check for README.md first, then README (without extension)
if [ -f "./README.md" ]; then
  README_FILE="./README.md"
elif [ -f "./README" ]; then
  README_FILE="./README"
else
  # README doesn't exist
  lunar collect -j ".repo.readme.exists" false
  exit 0
fi

# Count lines
LINES=$(wc -l < "$README_FILE" | tr -d ' ')

# Extract sections (headers starting with #, ##, ###, etc.)
# Remove the # symbols, strip markdown links/badges (everything from [ onwards), and trim whitespace
SECTIONS=$(grep -E '^#{1,6}\s+' "$README_FILE" | sed 's/^#\{1,6\}\s*//' | sed 's/\s*\[.*$//' | sed 's/^\s*//;s/\s*$//' | jq -R . | jq -s .)

# Build JSON object
JSON=$(jq -n \
  --argjson exists true \
  --argjson lines "$LINES" \
  --argjson sections "$SECTIONS" \
  '{
    exists: $exists,
    lines: $lines,
    sections: $sections
  }')

echo "$JSON" | lunar collect -j ".repo.readme" -
