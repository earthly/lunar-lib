#!/bin/bash

# LUNAR_COMPONENT_ID / LUNAR_COMPONENT_PR / LUNAR_SECRET_* / LUNAR_VAR_* are all
# injected by the Lunar runtime — they are not local assignments or typos.
# shellcheck disable=SC2153
set -e

# Populate .vcs.pr.* with the metadata of the merge request being evaluated.
# GitLab equivalent of github/pull_request.sh. Runs only in MR context; this is
# the GitLab source of .vcs.pr.* that the ticket collectors read via after-json.

# Only run in merge-request context.
if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  echo "Not in a merge-request context (LUNAR_COMPONENT_PR unset), skipping." >&2
  exit 0
fi

GITLAB_HOST="${LUNAR_VAR_GITLAB_HOST:-gitlab.com}"
HOST="${LUNAR_COMPONENT_ID%%/*}"

# Only process components on the configured GitLab host.
if [ "$HOST" != "$GITLAB_HOST" ]; then
  echo "Skipping: LUNAR_COMPONENT_ID host '${HOST:-<unset>}' != gitlab_host '${GITLAB_HOST}'." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_GL_TOKEN:-}" ]; then
  echo "Error: LUNAR_SECRET_GL_TOKEN is not set. Configure the GL_TOKEN secret for this collector." >&2
  exit 1
fi

# The project path is everything after the host. GitLab groups can nest
# (group/subgroup/project), so URL-encode the full path ('/' -> '%2F') for the
# API rather than assuming a fixed owner/repo depth.
PROJECT_PATH="${LUNAR_COMPONENT_ID#*/}"
PROJECT_ENC=$(printf '%s' "$PROJECT_PATH" | sed 's#/#%2F#g')

API_BASE="https://${HOST}/api/v4"

gl_api() {
  curl -sSL -H "PRIVATE-TOKEN: ${LUNAR_SECRET_GL_TOKEN}" "${API_BASE}$1"
}

MR=$(gl_api "/projects/${PROJECT_ENC}/merge_requests/${LUNAR_COMPONENT_PR}")

# Bail gracefully (exit 0) if the API didn't return a usable MR object, so a
# transient failure doesn't discard other collectors' data for this run.
if [ -z "$MR" ] || [ "$(echo "$MR" | jq -r 'has("iid")' 2>/dev/null)" != "true" ]; then
  echo "Unable to fetch merge request ${LUNAR_COMPONENT_PR} for ${PROJECT_PATH}." >&2
  exit 0
fi

TITLE=$(echo "$MR" | jq -r '.title // empty')
DESCRIPTION=$(echo "$MR" | jq -r '.description // empty')
URL=$(echo "$MR" | jq -r '.web_url // empty')
SOURCE_BRANCH=$(echo "$MR" | jq -r '.source_branch // empty')
TARGET_BRANCH=$(echo "$MR" | jq -r '.target_branch // empty')
AUTHOR=$(echo "$MR" | jq -r '.author.username // empty')
STATE=$(echo "$MR" | jq -r '.state // empty')
IID=$(echo "$MR" | jq '.iid')
# .draft is the modern field; .work_in_progress is the legacy alias.
DRAFT=$(echo "$MR" | jq '.draft // .work_in_progress // false')
LABELS=$(echo "$MR" | jq -c '.labels // []')

lunar collect \
  ".vcs.pr.title" "$TITLE" \
  ".vcs.pr.description" "$DESCRIPTION" \
  ".vcs.pr.url" "$URL" \
  ".vcs.pr.source_branch" "$SOURCE_BRANCH" \
  ".vcs.pr.target_branch" "$TARGET_BRANCH" \
  ".vcs.pr.author" "$AUTHOR" \
  ".vcs.pr.state" "$STATE"

lunar collect -j \
  ".vcs.pr.number" "$IID" \
  ".vcs.pr.draft" "$DRAFT"

echo "$LABELS" | lunar collect -j ".vcs.pr.labels" -
