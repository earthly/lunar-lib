#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Find the first matching exercise directory from candidate list
EXERCISE_DIR=""
if [ -n "$LUNAR_VAR_EXERCISE_DIR_PATHS" ]; then
  IFS=',' read -ra candidates <<< "$LUNAR_VAR_EXERCISE_DIR_PATHS"
  for candidate in "${candidates[@]}"; do
    candidate=$(echo "$candidate" | xargs)
    if [ -n "$candidate" ] && [ -d "./$candidate" ]; then
      EXERCISE_DIR="$candidate"
      break
    fi
  done
fi

if [ -z "$EXERCISE_DIR" ]; then
  lunar collect -j ".oncall.disaster_recovery" '{"exercise_count": 0, "exercises": []}'
  exit 0
fi

# Find all YYYY-MM-DD*.md files (allows date-arbitrary-text.md), sorted newest first
FILES=$(find "./$EXERCISE_DIR" -maxdepth 1 -type f -name '????-??-??*.md' | sort -r)

if [ -z "$FILES" ]; then
  lunar collect -j ".oncall.disaster_recovery" '{"exercise_count": 0, "exercises": []}'
  exit 0
fi

# Process each exercise file into a JSON array
EXERCISES="[]"
for file in $FILES; do
  path="${file#./}"
  filename=$(basename "$file" .md)

  # Extract date prefix (YYYY-MM-DD) from filename
  date="${filename:0:10}"

  FM=$(extract_frontmatter "$file")
  BODY=$(extract_body "$file")
  SECTIONS=$(extract_sections "$BODY")

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
