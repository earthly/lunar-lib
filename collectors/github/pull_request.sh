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
  ".vcs.pr.state" "$STATE"

lunar collect -j \
  ".vcs.pr.number" "$NUMBER" \
  ".vcs.pr.draft" "$DRAFT"

echo "$LABELS" | lunar collect -j ".vcs.pr.labels" -
