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
# Usage: extract_frontmatter "$filepath"
extract_frontmatter() {
  awk '/^---$/{if(n++)exit;next}n' "$1"
}

# Parse a single field from frontmatter YAML.
# Usage: parse_field "$frontmatter_text" "field_name"
parse_field() {
  local fm="$1" field="$2"
  if [ -z "$fm" ]; then echo ""; return; fi
  echo "$fm" | yq -r ".$field // empty" 2>/dev/null || echo ""
}

# Compute days elapsed since a date string (YYYY-MM-DD or ISO 8601).
# Returns empty string if date is empty or unparseable.
days_since() {
  local date_str="$1"
  if [ -z "$date_str" ]; then echo ""; return; fi
  local epoch
  epoch=$(date -d "$date_str" +%s 2>/dev/null) || { echo ""; return; }
  local now
  now=$(date +%s)
  echo $(( (now - epoch) / 86400 ))
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
# If no frontmatter exists, returns the whole file.
# Usage: extract_body "$filepath"
extract_body() {
  local fm
  fm=$(extract_frontmatter "$1")
  if [ -z "$fm" ]; then
    cat "$1"
  else
    awk '/^---$/{n++; next} n>=2' "$1"
  fi
}
