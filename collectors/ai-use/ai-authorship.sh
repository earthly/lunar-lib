#!/bin/bash
set -e

# Collect AI authorship annotation data from commits.
# Supports two mechanisms:
#   a) Git AI standard — refs/notes/ai (line-level, automated)
#   b) Git trailers — AI-model:, AI-tool:, etc. (lightweight, manual)

ANNOTATION_PREFIX="$LUNAR_VAR_ANNOTATION_PREFIX"
WINDOW="$LUNAR_VAR_DEFAULT_BRANCH_WINDOW"

# Determine commit range
if [ -n "$LUNAR_COMPONENT_PR" ] && [ -n "$LUNAR_COMPONENT_BASE_BRANCH" ]; then
  # PR context: commits in the PR
  COMMITS=$(git log --format='%H' "origin/$LUNAR_COMPONENT_BASE_BRANCH..HEAD" 2>/dev/null || true)
else
  # Default branch: recent commits
  COMMITS=$(git log --format='%H' -n "$WINDOW" 2>/dev/null || true)
fi

if [ -z "$COMMITS" ]; then
  jq -n '{
    provider: "none",
    total_commits: 0,
    annotated_commits: 0
  }' | lunar collect -j ".ai_use.authorship" -
  exit 0
fi

TOTAL=$(echo "$COMMITS" | wc -l | tr -d ' ')

# Try Git AI standard first (refs/notes/ai)
GIT_AI_REF_EXISTS=false
GIT_AI_COUNT=0

if git notes --ref=ai list >/dev/null 2>&1; then
  GIT_AI_REF_EXISTS=true

  while IFS= read -r sha; do
    [ -z "$sha" ] && continue
    if git notes --ref=ai show "$sha" >/dev/null 2>&1; then
      GIT_AI_COUNT=$((GIT_AI_COUNT + 1))
    fi
  done <<< "$COMMITS"
fi

# If Git AI found annotations, report that
if [ "$GIT_AI_REF_EXISTS" = true ] && [ "$GIT_AI_COUNT" -gt 0 ]; then
  jq -n \
    --arg provider "git-ai" \
    --argjson total "$TOTAL" \
    --argjson annotated "$GIT_AI_COUNT" \
    --argjson ref_exists "$GIT_AI_REF_EXISTS" \
    '{
      provider: $provider,
      total_commits: $total,
      annotated_commits: $annotated,
      git_ai: {
        notes_ref_exists: $ref_exists,
        commits_with_notes: $annotated
      }
    }' | lunar collect -j ".ai_use.authorship" -
  exit 0
fi

# Fallback: check git trailers
TRAILER_COUNT=0
TRAILER_DETAILS="[]"

while IFS= read -r sha; do
  [ -z "$sha" ] && continue

  # Check for trailers matching the prefix (e.g., AI-model:, AI-tool:)
  TRAILERS=$(git log -1 --format='%(trailers:key)' "$sha" 2>/dev/null || true)

  HAS_ANNOTATION=false
  MODEL=""
  TOKENS=""

  if [ -n "$ANNOTATION_PREFIX" ] && echo "$TRAILERS" | grep -qi "^${ANNOTATION_PREFIX}" 2>/dev/null; then
    HAS_ANNOTATION=true
    TRAILER_COUNT=$((TRAILER_COUNT + 1))

    # Extract specific trailer values
    MODEL=$(git log -1 --format="%(trailers:key=${ANNOTATION_PREFIX}model,valueonly)" "$sha" 2>/dev/null | head -1 | xargs || true)
    TOKENS=$(git log -1 --format="%(trailers:key=${ANNOTATION_PREFIX}tokens,valueonly)" "$sha" 2>/dev/null | head -1 | xargs || true)
  fi

  SHORT_SHA=$(echo "$sha" | cut -c1-8)

  ENTRY=$(jq -n \
    --arg sha "$SHORT_SHA" \
    --argjson has_annotation "$HAS_ANNOTATION" \
    --arg model "$MODEL" \
    --arg tokens "$TOKENS" \
    '{
      sha: $sha,
      has_annotation: $has_annotation,
      model: ($model | select(. != "")),
      tokens: (if $tokens != "" then ($tokens | tonumber? // null) else null end)
    }')

  TRAILER_DETAILS=$(echo "$TRAILER_DETAILS" | jq --argjson entry "$ENTRY" '. + [$entry]')
done <<< "$COMMITS"

PROVIDER="trailers"

jq -n \
  --arg provider "$PROVIDER" \
  --argjson total "$TOTAL" \
  --argjson annotated "$TRAILER_COUNT" \
  --argjson ref_exists "$GIT_AI_REF_EXISTS" \
  --argjson details "$TRAILER_DETAILS" \
  '{
    provider: $provider,
    total_commits: $total,
    annotated_commits: $annotated,
    git_ai: {
      notes_ref_exists: $ref_exists,
      commits_with_notes: 0
    },
    trailers: $details
  }' | lunar collect -j ".ai_use.authorship" -
