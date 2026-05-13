#!/bin/bash
set -e

WINDOW="${LUNAR_VAR_SIGNED_COMMITS_WINDOW:-50}"

# Resolve the default branch. Prefer the harness-supplied
# LUNAR_COMPONENT_BASE_BRANCH (set on every collection — authoritative
# and works in detached-HEAD PR checkouts). Fall back to local refs only
# if the env var is missing.
DEFAULT_BRANCH="${LUNAR_COMPONENT_BASE_BRANCH:-}"

if [ -z "$DEFAULT_BRANCH" ]; then
  if head_ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null); then
    DEFAULT_BRANCH="${head_ref#refs/remotes/origin/}"
  fi
fi

if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  # In a detached HEAD, rev-parse returns the literal "HEAD" — treat as unset.
  [ "$DEFAULT_BRANCH" = "HEAD" ] && DEFAULT_BRANCH=""
fi

emit_signing() {
  local branch="$1" examined="$2" good="$3" bad="$4" unknown="$5" \
    unsigned="$6" expired="$7" revoked="$8"
  jq -n \
    --arg default_branch "$branch" \
    --argjson commits_examined "$examined" \
    --argjson good "$good" \
    --argjson bad "$bad" \
    --argjson unknown "$unknown" \
    --argjson unsigned "$unsigned" \
    --argjson expired "$expired" \
    --argjson revoked "$revoked" \
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
}

if [ -z "$DEFAULT_BRANCH" ]; then
  echo "git: could not determine default branch" >&2
  emit_signing "<unknown>" 0 0 0 0 0 0 0
  exit 0
fi

# Inspect the last N commits on the default branch. Prefer the canonical
# remote ref, but fall back through alternatives if it yields nothing —
# in PR-checkout environments the remote-tracking ref can exist as a
# pointer while the underlying objects aren't in the local clone, and
# `git log` then silently returns empty.
RANGE=""
CODES=""
for candidate in \
  "refs/remotes/origin/$DEFAULT_BRANCH" \
  "refs/heads/$DEFAULT_BRANCH" \
  "HEAD"; do
  if codes=$(git log -n "$WINDOW" --pretty=format:'%G?' "$candidate" 2>/dev/null) \
    && [ -n "$codes" ]; then
    RANGE="$candidate"
    CODES="$codes"
    break
  fi
done

if [ -z "$RANGE" ]; then
  echo "git: no commits resolvable for '$DEFAULT_BRANCH'" >&2
  emit_signing "$DEFAULT_BRANCH" 0 0 0 0 0 0 0
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

emit_signing "$DEFAULT_BRANCH" "$EXAMINED" \
  "$GOOD" "$BAD" "$UNKNOWN" "$UNSIGNED" "$EXPIRED" "$REVOKED"
