#!/bin/bash

set -e

README_FILE="./README.md"

if [ -f "$README_FILE" ]; then
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
else
  # README doesn't exist
  JSON=$(jq -n \
    --argjson exists false \
    '{
      exists: $exists
    }')
  
  echo "$JSON" | lunar collect -j ".repo.readme" -
fi
