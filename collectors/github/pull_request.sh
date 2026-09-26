#!/bin/bash

# LUNAR_COMPONENT_ID / LUNAR_COMPONENT_PR / LUNAR_SECRET_* are injected by the
# Lunar runtime — they are not local assignments or typos of each other.
# shellcheck disable=SC2153
set -e

# Populate .vcs.pr.* with the metadata of the pull request being evaluated.
# This is the GitHub source of .vcs.pr.* that the ticket collectors read via
# their after-json variants. Runs only in PR context.

if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a pull-request context (LUNAR_COMPONENT_PR unset), skipping." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "Error: LUNAR_SECRET_GH_TOKEN is not set. Configure the GH_TOKEN secret for this collector." >&2
  exit 1
fi

# Component IDs are <host>/<owner>/<repository>[/<subpath>...]; monorepo
# components append the component path after the repository. Keep only
# owner/repository for the API URL, and route GHES hosts to /api/v3.
HOST="${LUNAR_COMPONENT_ID%%/*}"
REST="${LUNAR_COMPONENT_ID#*/}"
OWNER="${REST%%/*}"
REST="${REST#*/}"
REPO="${OWNER}/${REST%%/*}"

API_BASE="https://api.github.com"
if [ "$HOST" != "github.com" ]; then
  API_BASE="https://${HOST}/api/v3"
fi

# Every page of a list endpoint, each reduced by the jq filter in $2, merged
# into one JSON array on stdout. Retries transient failures; returns non-zero
# on any other non-200 page or a non-array body, so a caller never writes a
# partial list.
gh_list() {
  local url="$1" filter="$2" page=1 attempt resp code body reduced all='[]'
  while [ "$page" -le 10 ]; do
    attempt=1
    while :; do
      resp=$(curl -sSL -w $'\n%{http_code}' \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "${url}?per_page=100&page=${page}" 2>/dev/null) || resp=$'\n000'
      code=$(printf '%s\n' "$resp" | tail -n1)
      case "$code" in
        000 | 429 | 5[0-9][0-9])
          if [ "$attempt" -lt 3 ]; then
            sleep "$attempt"
            attempt=$((attempt + 1))
            continue
          fi
          ;;
      esac
      break
    done
    [ "$code" = "200" ] || return 1
    body=$(printf '%s\n' "$resp" | sed '$d')
    printf '%s' "$body" | jq -e 'type == "array"' > /dev/null 2>&1 || return 1
    reduced=$(printf '%s\n' "$body" | jq -c "$filter") || return 1
    all=$(printf '%s\n%s\n' "$all" "$reduced" | jq -cs 'add') || return 1
    [ "$(printf '%s' "$body" | jq 'length')" -lt 100 ] && break
    page=$((page + 1))
  done
  printf '%s\n' "$all"
}

PR=$(curl -sSL \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "${API_BASE}/repos/${REPO}/pulls/${LUNAR_COMPONENT_PR}")

# Bail gracefully (exit 0) if the API didn't return a usable PR object, so a
# transient failure doesn't discard other collectors' data for this run.
if [ -z "$PR" ] || [ "$(echo "$PR" | jq -r 'has("number")' 2>/dev/null)" != "true" ]; then
  echo "Unable to fetch pull request ${LUNAR_COMPONENT_PR} for ${REPO}." >&2
  exit 0
fi

TITLE=$(echo "$PR" | jq -r '.title // empty')
DESCRIPTION=$(echo "$PR" | jq -r '.body // empty')
URL=$(echo "$PR" | jq -r '.html_url // empty')
SOURCE_BRANCH=$(echo "$PR" | jq -r '.head.ref // empty')
TARGET_BRANCH=$(echo "$PR" | jq -r '.base.ref // empty')
AUTHOR=$(echo "$PR" | jq -r '.user.login // empty')
# GitHub's .state is only open/closed; surface merged as its own state.
STATE=$(echo "$PR" | jq -r 'if .merged_at != null then "merged" else .state end')
HEAD_SHA=$(echo "$PR" | jq -r '.head.sha // empty')
COMMIT_COUNT=$(echo "$PR" | jq '.commits // 0')
NUMBER=$(echo "$PR" | jq '.number')
DRAFT=$(echo "$PR" | jq '.draft // false')
LABELS=$(echo "$PR" | jq -c '[.labels[]?.name]')

lunar collect \
  ".vcs.pr.title" "$TITLE" \
  ".vcs.pr.description" "$DESCRIPTION" \
  ".vcs.pr.url" "$URL" \
  ".vcs.pr.source_branch" "$SOURCE_BRANCH" \
  ".vcs.pr.target_branch" "$TARGET_BRANCH" \
  ".vcs.pr.author" "$AUTHOR" \
  ".vcs.pr.state" "$STATE" \
  ".vcs.pr.head_sha" "$HEAD_SHA"

lunar collect -j \
  ".vcs.pr.number" "$NUMBER" \
  ".vcs.pr.draft" "$DRAFT"

echo "$LABELS" | lunar collect -j ".vcs.pr.labels" -

# Reviews submitted so far, oldest first. Collection runs on pushes, not on
# review events, so an approval given after the last push is not here yet.
# Pending reviews are unsubmitted drafts and are left out.
if REVIEWS=$(gh_list "${API_BASE}/repos/${REPO}/pulls/${LUNAR_COMPONENT_PR}/reviews" \
  '[.[] | select(.state != "PENDING")
     | {reviewer: (.user.login // "ghost"), state, submitted_at, commit_sha: .commit_id}
     | with_entries(select(.value != null))]'); then
  echo "$REVIEWS" | lunar collect -j ".vcs.pr.reviews" -
else
  echo "Unable to list reviews for pull request ${LUNAR_COMPONENT_PR} on ${REPO}; .vcs.pr.reviews not collected." >&2
fi

# The PR's commits with GitHub's signature verification. The endpoint lists at
# most 250 commits, so a longer PR gets no list rather than a partial one.
if COMMITS=$(gh_list "${API_BASE}/repos/${REPO}/pulls/${LUNAR_COMPONENT_PR}/commits" \
  '[.[] | {sha, author: .author.login}
     + (if .commit.verification then {signature: {verified: .commit.verification.verified, reason: .commit.verification.reason}} else {} end)
     | with_entries(select(.value != null))]'); then
  if [ "$(echo "$COMMITS" | jq 'length')" -ge "$COMMIT_COUNT" ]; then
    echo "$COMMITS" | lunar collect -j ".vcs.pr.commits" -
  else
    echo "Pull request ${LUNAR_COMPONENT_PR} has ${COMMIT_COUNT} commits but GitHub lists at most 250; .vcs.pr.commits not collected." >&2
  fi
else
  echo "Unable to list commits for pull request ${LUNAR_COMPONENT_PR} on ${REPO}; .vcs.pr.commits not collected." >&2
fi
