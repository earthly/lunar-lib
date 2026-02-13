#!/bin/bash
# Shared helpers for dr-docs sub-collectors.

# Find the first matching file from a comma-separated candidate list.
# Usage: find_file "$LUNAR_VAR_SOME_PATH"
# Sets FOUND_FILE (empty if none found) and FOUND_PATH (normalized).
find_file() {
  local candidates_str="$1"
  FOUND_FILE=""
  FOUND_PATH=""

  IFS=',' read -ra candidates <<< "$candidates_str"
  for candidate in "${candidates[@]}"; do
    candidate=$(echo "$candidate" | xargs)
    if [ -f "./$candidate" ]; then
      FOUND_FILE="./$candidate"
      FOUND_PATH="${FOUND_FILE#./}"
      return 0
    fi
  done
  return 1
}

# Extract YAML frontmatter (text between first two --- markers).
# Only considers frontmatter if the file's first line is exactly ---.
# Usage: extract_frontmatter "$filepath"
extract_frontmatter() {
  local first_line
  first_line=$(head -n1 "$1")
  if [ "$first_line" != "---" ]; then echo ""; return; fi
  awk 'NR==1{next} /^---$/{exit} {print}' "$1"
}

# Parse a single field from frontmatter YAML.
# Usage: parse_field "$frontmatter_text" "field_name"
parse_field() {
  local fm="$1" field="$2"
  if [ -z "$fm" ]; then echo ""; return; fi
  echo "$fm" | yq -r ".$field // empty" 2>/dev/null || echo ""
}

# Extract markdown section headings from text (body content, not frontmatter).
# Usage: extract_sections "$body_text"
extract_sections() {
  echo "$1" | grep -E '^#{1,6}\s+' \
    | sed 's/^#\{1,6\}\s*//' \
    | sed 's/^\s*//;s/\s*$//' \
    | jq -R . | jq -s . || echo '[]'
}

# Extract the markdown body after YAML frontmatter.
# Only strips frontmatter if the file begins with ---.
# Usage: extract_body "$filepath"
extract_body() {
  local first_line
  first_line=$(head -n1 "$1")
  if [ "$first_line" != "---" ]; then
    cat "$1"
  else
    awk 'NR==1{next} /^---$/{found=1; next} found{print}' "$1"
  fi
}
