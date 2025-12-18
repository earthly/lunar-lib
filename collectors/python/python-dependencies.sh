#!/bin/bash
set -e

# Check if this is actually a Python project by looking for .py files
if ! find . -name "*.py" -type f 2>/dev/null | grep -q .; then
    echo "No Python files found, exiting"
    exit 0
fi

# Collect dependencies from requirements.txt (best effort)
if [[ -f "requirements.txt" ]]; then
  deps=()
  while IFS= read -r line; do
    # Strip comments and whitespace
    clean=$(echo "$line" | sed 's/#.*//' | tr -d '[:space:]')
    if [[ -z "$clean" ]]; then
      continue
    fi
    name="$clean"
    version=""
    if [[ "$clean" == *"=="* ]]; then
      name="${clean%%==*}"
      version="${clean#*==}"
    fi
    deps+=("$(jq -n --arg path "$name" --arg version "$version" '{path: $path, version: ($version | select(. != "")), indirect: false, replace: null, license: ""}')")
  done < requirements.txt

  jq -n \
    --argjson direct "$(printf '%s\n' "${deps[@]}" | jq -s '.')" \
    '{direct: $direct, transitive: []}' | lunar collect -j ".lang.python.dependencies" -
else
  # No requirements.txt, exit without collecting
  echo "No requirements.txt found, exiting"
  exit 0
fi

