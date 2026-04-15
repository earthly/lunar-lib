#!/bin/bash
set -e

# Discover CLAUDE.md instruction files.
# Writes to both ai.native.claude.instruction_file and ai.instructions.all[]
# for normalized cross-tool access.

FILES=$(find . \( -type f -o -type l \) -name CLAUDE.md -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null || true)

if [ -z "$FILES" ]; then
  exit 0
fi

# Use the first file found (prefer root)
ROOT_FILE=""
FIRST_FILE=""
while IFS= read -r file; do
  [ -z "$file" ] && continue
  FIRST_FILE="${FIRST_FILE:-$file}"
  filepath="${file#./}"
  dirpath=$(dirname "$filepath")
  if [ "$dirpath" = "." ]; then
    ROOT_FILE="$file"
    break
  fi
done <<< "$FILES"

FILE="${ROOT_FILE:-$FIRST_FILE}"
filepath="${FILE#./}"

if [ -r "$FILE" ]; then
  lines=$(wc -l < "$FILE" | tr -d ' ')
  bytes=$(wc -c < "$FILE" | tr -d ' ')
else
  lines=0
  bytes=0
fi

is_symlink=false
symlink_target="null"
if [ -L "$FILE" ]; then
  is_symlink=true
  target=$(readlink "$FILE")
  symlink_target=$(jq -n --arg t "$target" '$t')
fi

# Write to native path
jq -n \
  --argjson exists true \
  --arg path "$filepath" \
  --argjson lines "$lines" \
  --argjson bytes "$bytes" \
  --argjson is_symlink "$is_symlink" \
  --argjson symlink_target "$symlink_target" \
  '{
    exists: $exists,
    path: $path,
    lines: $lines,
    bytes: $bytes,
    is_symlink: $is_symlink,
    symlink_target: $symlink_target
  }' | lunar collect -j ".ai.native.claude.instruction_file" -

# Also append to normalized array for cross-tool access
while IFS= read -r file; do
  [ -z "$file" ] && continue
  filepath="${file#./}"
  dirpath=$(dirname "$filepath")
  filename=$(basename "$filepath")

  if [ -r "$file" ]; then
    flines=$(wc -l < "$file" | tr -d ' ')
    fbytes=$(wc -c < "$file" | tr -d ' ')
  else
    flines=0
    fbytes=0
  fi

  fis_symlink=false
  fsymlink_target="null"
  if [ -L "$file" ]; then
    fis_symlink=true
    ftarget=$(readlink "$file")
    fsymlink_target=$(jq -n --arg t "$ftarget" '$t')
  fi

  jq -n \
    --arg path "$filepath" \
    --arg dir "$dirpath" \
    --arg filename "$filename" \
    --argjson lines "$flines" \
    --argjson bytes "$fbytes" \
    --argjson is_symlink "$fis_symlink" \
    --argjson symlink_target "$fsymlink_target" \
    '{
      path: $path,
      dir: $dir,
      filename: $filename,
      lines: $lines,
      bytes: $bytes,
      is_symlink: $is_symlink,
      symlink_target: $symlink_target
    }' | lunar collect -j ".ai.instructions.all[]" -
done <<< "$FILES"
