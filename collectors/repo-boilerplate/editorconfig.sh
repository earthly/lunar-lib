#!/bin/bash

set -e

if [ ! -f ".editorconfig" ]; then
  lunar collect -j ".repo.editorconfig.exists" false
  exit 0
fi

# Count section blocks (lines matching [pattern])
SECTION_COUNT=$(grep -c '^\[' ".editorconfig" 2>/dev/null || echo 0)

JSON=$(jq -n \
  --argjson exists true \
  --arg path ".editorconfig" \
  --argjson sections "$SECTION_COUNT" \
  '{
    exists: $exists,
    path: $path,
    sections: $sections
  }')

echo "$JSON" | lunar collect -j ".repo.editorconfig" -
