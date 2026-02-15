#!/bin/bash
set -e

# Discover all agent instruction files (AGENTS.md, CLAUDE.md, etc.) across the repo.
# Records per-file metadata, per-directory grouping, and root-level summary.

# Find all instruction files using the configurable find command
FILES=$(eval "$LUNAR_VAR_MD_FIND_COMMAND" 2>/dev/null || true)

if [ -z "$FILES" ]; then
  # No instruction files found anywhere
  jq -n '{
    root: { exists: false },
    all: [],
    count: 0,
    total_bytes: 0,
    directories: [],
    source: { tool: "find", integration: "code" }
  }' | lunar collect -j ".ai_use.instructions" -
  exit 0
fi

# Build per-file JSON array
ALL_FILES="[]"
while IFS= read -r file; do
  [ -z "$file" ] && continue

  # Normalize path (remove leading ./)
  filepath="${file#./}"
  dirpath=$(dirname "$filepath")
  filename=$(basename "$filepath")

  # Line count
  lines=$(wc -l < "$file" | tr -d ' ')

  # Byte size
  bytes=$(wc -c < "$file" | tr -d ' ')

  # Extract markdown section headings
  sections=$(grep -E '^#{1,6}\s+' "$file" 2>/dev/null \
    | sed 's/^#\{1,6\}\s*//' \
    | sed 's/\s*\[.*$//' \
    | sed 's/^\s*//;s/\s*$//' \
    | jq -R . | jq -s . || echo '[]')

  # Check if symlink
  is_symlink=false
  symlink_target="null"
  if [ -L "$file" ]; then
    is_symlink=true
    target=$(readlink "$file")
    symlink_target=$(jq -n --arg t "$target" '$t')
  fi

  # Build file entry
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

# Count files
COUNT=$(echo "$ALL_FILES" | jq 'length')

# Total bytes (non-symlink files only)
TOTAL_BYTES=$(echo "$ALL_FILES" | jq '[.[] | select(.is_symlink == false) | .bytes] | add // 0')

# Build root info (first instruction file found in repo root directory ".")
ROOT_INFO=$(echo "$ALL_FILES" | jq '
  [.[] | select(.dir == ".")] |
  if length > 0 then
    # Prefer non-symlink file at root
    (([.[] | select(.is_symlink == false)] | first) // first) |
    { exists: true, filename: .filename, lines: .lines, bytes: .bytes, sections: .sections }
  else
    { exists: false }
  end
')

# Build per-directory grouping
DIRECTORIES=$(echo "$ALL_FILES" | jq '
  group_by(.dir) | map({
    dir: .[0].dir,
    files: [.[] | {
      filename: .filename,
      is_symlink: .is_symlink
    } + (if .is_symlink then { symlink_target: .symlink_target } else {} end)]
  })
')

# Assemble final output
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
  }' | lunar collect -j ".ai_use.instructions" -
