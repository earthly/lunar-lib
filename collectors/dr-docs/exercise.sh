#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

EXERCISE_DIR="$LUNAR_VAR_EXERCISE_DIR"

# Check if directory exists
if [ ! -d "./$EXERCISE_DIR" ]; then
  lunar collect -j ".oncall.disaster_recovery" '{"exercise_count": 0, "exercises": []}'
  exit 0
fi

# Find all YYYY-MM-DD.md files, sorted newest first
FILES=$(find "./$EXERCISE_DIR" -maxdepth 1 -type f -name '????-??-??.md' | sort -r)

if [ -z "$FILES" ]; then
  lunar collect -j ".oncall.disaster_recovery" '{"exercise_count": 0, "exercises": []}'
  exit 0
fi

# Process each exercise file into a JSON array
EXERCISES="[]"
for file in $FILES; do
  path="${file#./}"
  filename=$(basename "$file" .md)

  # Date is the filename itself (YYYY-MM-DD)
  date="$filename"

  FM=$(extract_frontmatter "$file")
  BODY=$(extract_body "$file")
  SECTIONS=$(extract_sections "$BODY")

  # Frontmatter can override date or add exercise_type
  fm_date=$(parse_field "$FM" "date")
  if [ -n "$fm_date" ]; then
    date="$fm_date"
  fi
  exercise_type=$(parse_field "$FM" "exercise_type")

  ENTRY=$(jq -n \
    --arg date "$date" \
    --arg path "$path" \
    --arg et "$exercise_type" \
    --argjson sections "${SECTIONS:-[]}" \
    '{date: $date, path: $path}
     + if $et != "" then {exercise_type: $et} else {} end
     + {sections: $sections}')

  EXERCISES=$(echo "$EXERCISES" | jq --argjson entry "$ENTRY" '. + [$entry]')
done

# Compute summary from the most recent exercise (first in sorted list)
LATEST_DATE=$(echo "$EXERCISES" | jq -r '.[0].date')
DAYS_SINCE=$(days_since "$LATEST_DATE")
COUNT=$(echo "$EXERCISES" | jq 'length')

# Build result
jq -n \
  --argjson exercises "$EXERCISES" \
  --arg latest "$LATEST_DATE" \
  --arg days "$DAYS_SINCE" \
  --argjson count "$COUNT" \
  '{exercises: $exercises, latest_exercise_date: $latest}
   + if $days != "" then {days_since_latest_exercise: ($days | tonumber)} else {} end
   + {exercise_count: $count}' \
  | lunar collect -j ".oncall.disaster_recovery" -
