#!/bin/bash
set -e

# Check for a dedicated AI plans directory.
# Tries candidate paths in order (first match wins).

IFS=',' read -ra CANDIDATES <<< "$LUNAR_VAR_PLANS_DIR_PATHS"

PLANS_DIR=""
for candidate in "${CANDIDATES[@]}"; do
  candidate=$(echo "$candidate" | xargs)  # trim whitespace
  if [ -d "$candidate" ]; then
    PLANS_DIR="$candidate"
    break
  fi
done

if [ -z "$PLANS_DIR" ]; then
  lunar collect -j ".ai_use.plans_dir" '{"exists": false}'
  exit 0
fi

# Count files (non-recursive, exclude hidden files)
FILE_COUNT=$(find "$PLANS_DIR" -maxdepth 1 -type f -not -name '.*' 2>/dev/null | wc -l | tr -d ' ')

jq -n \
  --argjson exists true \
  --arg path "$PLANS_DIR" \
  --argjson file_count "$FILE_COUNT" \
  '{
    exists: $exists,
    path: $path,
    file_count: $file_count
  }' | lunar collect -j ".ai_use.plans_dir" -
