#!/bin/bash

set -e

CHANGELOG_PATHS="${LUNAR_VAR_CHANGELOG_PATHS:-CHANGELOG.md,CHANGELOG,CHANGES.md,HISTORY.md,RELEASES.md}"

CHANGELOG_FILE=""
IFS=',' read -ra CANDIDATES <<< "$CHANGELOG_PATHS"
for candidate in "${CANDIDATES[@]}"; do
  trimmed="${candidate#"${candidate%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  if [ -n "$trimmed" ] && [ -f "./$trimmed" ]; then
    CHANGELOG_FILE="./$trimmed"
    break
  fi
done

if [ -z "$CHANGELOG_FILE" ]; then
  lunar collect -j ".repo.changelog.exists" false
  exit 0
fi

PATH_NORMALIZED="${CHANGELOG_FILE#./}"

LINES=$(wc -l < "$CHANGELOG_FILE" | tr -d ' ')

# Note: unlike the other repo-boilerplate collectors, we don't strip trailing
# `[...]` from section titles — Keep-a-Changelog headings like "[1.2.0] - 2026-05-01"
# carry the version in brackets, so stripping them would empty every entry.
SECTIONS=$(grep -E '^#{1,6}\s+' "$CHANGELOG_FILE" 2>/dev/null | sed 's/^#\{1,6\}\s*//' | sed 's/^\s*//;s/\s*$//' | jq -R . | jq -s . || echo '[]')

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

echo "$JSON" | lunar collect -j ".repo.changelog" -
