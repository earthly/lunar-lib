#!/bin/bash
set -e

# Discover AGENTS.md instruction files across the repo.
# Records per-file metadata, per-directory grouping, and root-level summary.
# Tool-specific files (CLAUDE.md, CODEX.md, GEMINI.md) are handled by their
# respective tool collectors.

FILES=$(eval "$LUNAR_VAR_MD_FIND_COMMAND" 2>/dev/null || true)

if [ -z "$FILES" ]; then
  jq -n '{
    root: { exists: false },
    all: [],
    count: 0,
    total_bytes: 0,
    directories: [],
    source: { tool: "find", integration: "code" }
  }' | lunar collect -j ".ai.instructions" -
  exit 0
fi

# Build per-file JSON array
ALL_FILES="[]"
while IFS= read -r file; do
  [ -z "$file" ] && continue

  filepath="${file#./}"
  dirpath=$(dirname "$filepath")
  filename=$(basename "$filepath")

  if [ -r "$file" ]; then
    lines=$(wc -l < "$file" | tr -d ' ')
    bytes=$(wc -c < "$file" | tr -d ' ')
    sections=$(grep -E '^#{1,6}\s+' "$file" 2>/dev/null \
      | sed 's/^#\{1,6\}\s*//' \
      | sed 's/\s*\[.*$//' \
      | sed 's/^\s*//;s/\s*$//' \
      | jq -R . | jq -s . || echo '[]')
  else
    lines=0
    bytes=0
    sections='[]'
  fi

  is_symlink=false
  symlink_target="null"
  if [ -L "$file" ]; then
    is_symlink=true
    target=$(readlink "$file")
    symlink_target=$(jq -n --arg t "$target" '$t')
  fi

  entry=$(jq -n \
    --arg path "$filepath" \
    --arg dir "$dirpath" \
    --arg filename "$filename" \
    --argjson lines "$lines" \
    --argjson bytes "$bytes" \
    --argjson sections "$sections" \
    --argjson is_symlink "$is_symlink" \
    --argjson symlink_target "$symlink_target" \
    '{
      path: $path,
      dir: $dir,
      filename: $filename,
      lines: $lines,
      bytes: $bytes,
      sections: $sections,
      is_symlink: $is_symlink,
      symlink_target: $symlink_target
    }')

  ALL_FILES=$(echo "$ALL_FILES" | jq --argjson entry "$entry" '. + [$entry]')
done <<< "$FILES"

COUNT=$(echo "$ALL_FILES" | jq 'length')
TOTAL_BYTES=$(echo "$ALL_FILES" | jq '[.[] | select(.is_symlink == false) | .bytes] | add // 0')

ROOT_INFO=$(echo "$ALL_FILES" | jq '
  [.[] | select(.dir == ".")] |
  if length > 0 then
    (([.[] | select(.is_symlink == false)] | first) // first) |
    { exists: true, filename: .filename, lines: .lines, bytes: .bytes, sections: .sections }
  else
    { exists: false }
  end
')

DIRECTORIES=$(echo "$ALL_FILES" | jq '
  group_by(.dir) | map({
    dir: .[0].dir,
    files: [.[] | {
      filename: .filename,
      is_symlink: .is_symlink
    } + (if .is_symlink then { symlink_target: .symlink_target } else {} end)]
  })
')

jq -n \
  --argjson root "$ROOT_INFO" \
  --argjson all "$ALL_FILES" \
  --argjson count "$COUNT" \
  --argjson total_bytes "$TOTAL_BYTES" \
  --argjson directories "$DIRECTORIES" \
  '{
    root: $root,
    all: $all,
    count: $count,
    total_bytes: $total_bytes,
    directories: $directories,
    source: { tool: "find", integration: "code" }
  }' | lunar collect -j ".ai.instructions" -
