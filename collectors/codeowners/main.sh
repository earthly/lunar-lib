#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$0")"

# Convert comma-separated paths input to array
IFS=',' read -ra CODEOWNERS_CANDIDATES <<< "$LUNAR_VAR_PATHS"

# Find the first matching CODEOWNERS file
CODEOWNERS_FILE=""
for candidate in "${CODEOWNERS_CANDIDATES[@]}"; do
  if [ -f "./$candidate" ]; then
    CODEOWNERS_FILE="./$candidate"
    break
  fi
done

# No CODEOWNERS file found
if [ -z "$CODEOWNERS_FILE" ]; then
  lunar collect -j ".ownership.codeowners.exists" false
  exit 0
fi

# Normalize path (remove leading ./)
PATH_NORMALIZED="${CODEOWNERS_FILE#./}"

# Parse the CODEOWNERS file and add the path
python3 "$SCRIPT_DIR/parse_codeowners.py" "$CODEOWNERS_FILE" \
  | jq --arg path "$PATH_NORMALIZED" '. + {path: $path}' \
  | lunar collect -j ".ownership.codeowners" -
