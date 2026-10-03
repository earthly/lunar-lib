#!/bin/bash
# Shared helpers for compliance-docs sub-collectors.

# Print the first existing directory from a comma-separated candidate list.
# Usage: DIR=$(first_existing_dir "$LUNAR_VAR_SOME_DIR_PATHS")
first_existing_dir() {
  local candidate
  local -a candidates
  IFS=',' read -ra candidates <<< "$1"
  for candidate in "${candidates[@]}"; do
    candidate="${candidate#"${candidate%%[![:space:]]*}"}"
    candidate="${candidate%"${candidate##*[![:space:]]}"}"
    if [ -n "$candidate" ] && [ -d "./$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done
  return 0
}

# Print a file's YAML frontmatter: the lines between an opening --- on line 1
# and the next ---. Prints nothing when either delimiter is missing.
# Usage: extract_frontmatter "$filepath"
extract_frontmatter() {
  awk '
    NR == 1 { if ($0 !~ /^---\r?$/) exit; next }
    /^---\r?$/ { closed = 1; exit }
    { buf = buf $0 "\n" }
    END { if (closed) printf "%s", buf }
  ' "$1"
}

# Print a file's frontmatter as a compact JSON object ({} when there is none).
# Usage: frontmatter_json "$filepath"
frontmatter_json() {
  local fm json
  fm=$(extract_frontmatter "$1")
  if [ -z "$fm" ]; then
    echo '{}'
    return 0
  fi
  if ! json=$(printf '%s\n' "$fm" | yq -p=yaml -o=json -I=0 '.' 2>/dev/null); then
    echo "compliance-docs: ignoring unparseable frontmatter in ${1#./}" >&2
    echo '{}'
    return 0
  fi
  echo "${json:-null}" | jq -c 'if type == "object" then . else {} end'
}

# Succeed when $1 is a real calendar date in YYYY-MM-DD form.
# Usage: is_valid_date "2026-03-14"
is_valid_date() {
  [[ "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || return 1
  # strptime accepts days past the end of the month; the round trip rejects them.
  [ "$(jq -rn --arg d "$1" 'try ($d | strptime("%Y-%m-%d") | mktime | strftime("%Y-%m-%d")) catch ""')" = "$1" ]
}
