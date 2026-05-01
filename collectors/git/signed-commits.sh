#!/bin/bash
set -e

WINDOW="${LUNAR_VAR_SIGNED_COMMITS_WINDOW:-50}"

# Resolve the default branch. Try `git remote show origin` first
# (authoritative when the remote is reachable), then fall back to
# refs/remotes/origin/HEAD, then HEAD itself.
DEFAULT_BRANCH=""
if remote_show=$(git remote show origin 2>/dev/null); then
  DEFAULT_BRANCH=$(echo "$remote_show" | sed -n 's/^[[:space:]]*HEAD branch:[[:space:]]*//p' | head -1)
fi

if [ -z "$DEFAULT_BRANCH" ] || [ "$DEFAULT_BRANCH" = "(unknown)" ]; then
  if head_ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null); then
    DEFAULT_BRANCH="${head_ref#refs/remotes/origin/}"
  fi
fi

if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
fi

if [ -z "$DEFAULT_BRANCH" ]; then
  echo "git: could not determine default branch" >&2
  exit 0
fi

# Inspect the last N commits on the default branch. Prefer the remote
# ref (origin/<branch>) so we describe the canonical history regardless
# of local checkout state.
if git rev-parse --verify "refs/remotes/origin/$DEFAULT_BRANCH" >/dev/null 2>&1; then
  RANGE="refs/remotes/origin/$DEFAULT_BRANCH"
elif git rev-parse --verify "refs/heads/$DEFAULT_BRANCH" >/dev/null 2>&1; then
  RANGE="refs/heads/$DEFAULT_BRANCH"
else
  RANGE="HEAD"
fi

if ! CODES=$(git log -n "$WINDOW" --pretty=format:'%G?' "$RANGE" 2>/dev/null); then
  echo "git: log failed for $RANGE" >&2
  exit 0
fi

GOOD=0
BAD=0
UNKNOWN=0
UNSIGNED=0
EXPIRED=0
REVOKED=0
EXAMINED=0

while IFS= read -r code; do
  [ -z "$code" ] && continue
  EXAMINED=$((EXAMINED + 1))
  case "$code" in
    G) GOOD=$((GOOD + 1)) ;;
    B) BAD=$((BAD + 1)) ;;
    U) UNKNOWN=$((UNKNOWN + 1)) ;;
    N) UNSIGNED=$((UNSIGNED + 1)) ;;
    X) EXPIRED=$((EXPIRED + 1)) ;;
    R) REVOKED=$((REVOKED + 1)) ;;
    *) UNKNOWN=$((UNKNOWN + 1)) ;;
  esac
done <<< "$CODES"

jq -n \
  --arg default_branch "$DEFAULT_BRANCH" \
  --argjson commits_examined "$EXAMINED" \
  --argjson good "$GOOD" \
  --argjson bad "$BAD" \
  --argjson unknown "$UNKNOWN" \
  --argjson unsigned "$UNSIGNED" \
  --argjson expired "$EXPIRED" \
  --argjson revoked "$REVOKED" \
  '{
    default_branch: $default_branch,
    commits_examined: $commits_examined,
    signature_counts: {
      good: $good,
      bad: $bad,
      unknown: $unknown,
      unsigned: $unsigned,
      expired: $expired,
      revoked: $revoked
    }
  }' | lunar collect -j ".git.signing" -
