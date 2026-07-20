#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$0")"

# Where CODEOWNERS files may live (first match wins), relative to a base dir.
IFS=',' read -ra CODEOWNERS_CANDIDATES <<< "$LUNAR_VAR_CODEOWNERS_PATHS"

# How to locate the CODEOWNERS file (see lunar-collector.yml `codeowners_scope`):
#   auto          - component dir first, then fall back to the repo root (global)
#   component-dir - only the component's own directory
#   repo-root     - only the repository root (global CODEOWNERS)
SCOPE_MODE="${LUNAR_VAR_CODEOWNERS_SCOPE:-auto}"

COMPONENT_DIR="$PWD"

# Find the repository root. In a monorepo the collector runs from the
# component's subdirectory (the hub sets the working dir to <repo>/<subdir>),
# but a CODEOWNERS file is only honored by GitHub/GitLab at the repo root
# (root, .github/, docs/) — never in a component subdirectory. So we resolve
# the repo root to find the GLOBAL CODEOWNERS shared across the monorepo.
find_repo_root() {
  local root
  root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$root" ] && [ -d "$root" ]; then
    printf '%s\n' "$root"
    return
  fi
  # Fallback when git is unavailable: walk up looking for a .git entry
  # (a directory for a normal clone, a file for a worktree/submodule).
  local dir="$COMPONENT_DIR"
  while [ "$dir" != "/" ]; do
    if [ -e "$dir/.git" ]; then
      printf '%s\n' "$dir"
      return
    fi
    dir="$(dirname "$dir")"
  done
  # Last resort: assume the component dir is the repo root (single repo).
  printf '%s\n' "$COMPONENT_DIR"
}

REPO_ROOT="$(find_repo_root)"

# Search a base directory for the first matching CODEOWNERS candidate.
# Prints the file path on success; returns non-zero when none is found.
search_dir() {
  local base="$1" cand
  for cand in "${CODEOWNERS_CANDIDATES[@]}"; do
    if [ -f "$base/$cand" ]; then
      printf '%s\n' "$base/$cand"
      return 0
    fi
  done
  return 1
}

CODEOWNERS_FILE=""
MATCH_BASE=""

case "$SCOPE_MODE" in
  component-dir)
    if CODEOWNERS_FILE="$(search_dir "$COMPONENT_DIR")"; then MATCH_BASE="$COMPONENT_DIR"; fi
    ;;
  repo-root)
    if CODEOWNERS_FILE="$(search_dir "$REPO_ROOT")"; then MATCH_BASE="$REPO_ROOT"; fi
    ;;
  *)  # auto
    if CODEOWNERS_FILE="$(search_dir "$COMPONENT_DIR")"; then
      MATCH_BASE="$COMPONENT_DIR"
    elif [ "$COMPONENT_DIR" != "$REPO_ROOT" ] && CODEOWNERS_FILE="$(search_dir "$REPO_ROOT")"; then
      MATCH_BASE="$REPO_ROOT"
    fi
    ;;
esac

# No CODEOWNERS file found
if [ -z "$CODEOWNERS_FILE" ]; then
  lunar collect -j ".ownership.codeowners.exists" false
  exit 0
fi

# Record the path relative to the repo root (the canonical, forge-meaningful
# location such as ".github/CODEOWNERS") and whether the file was found at the
# repo root (global, shared across a monorepo -> "repo") or in the component's
# own directory ("component").
REL_PATH="${CODEOWNERS_FILE#"$REPO_ROOT"/}"
if [ "$MATCH_BASE" = "$REPO_ROOT" ]; then
  SCOPE="repo"
else
  SCOPE="component"
fi

# Parse the CODEOWNERS file and add the path + scope metadata.
python3 "$SCRIPT_DIR/parse_codeowners.py" "$CODEOWNERS_FILE" \
  | jq --arg path "$REL_PATH" --arg scope "$SCOPE" '. + {path: $path, scope: $scope}' \
  | lunar collect -j ".ownership.codeowners" -
