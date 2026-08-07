#!/bin/bash

set -e

# Collect GitLab project settings into the shared .vcs.* schema.

GITLAB_HOST="${LUNAR_VAR_GITLAB_HOST:-gitlab.com}"
HOST="${LUNAR_COMPONENT_ID%%/*}"

if [ "$HOST" != "$GITLAB_HOST" ]; then
  echo "Skipping: LUNAR_COMPONENT_ID host '${HOST:-<unset>}' != gitlab_host '${GITLAB_HOST}'." >&2
  exit 0
fi

if [ -z "${LUNAR_SECRET_GL_TOKEN:-}" ]; then
  echo "Error: LUNAR_SECRET_GL_TOKEN is not set. Configure the GL_TOKEN secret for this collector." >&2
  exit 1
fi

PROJECT_PATH="${LUNAR_COMPONENT_ID#*/}"
PROJECT_ENC=$(printf '%s' "$PROJECT_PATH" | sed 's#/#%2F#g')
API_BASE="https://${HOST}/api/v4"

gl_api() {
  curl -sSL -H "PRIVATE-TOKEN: ${LUNAR_SECRET_GL_TOKEN}" "${API_BASE}$1"
}

PROJECT=$(gl_api "/projects/${PROJECT_ENC}")
if [ -z "$PROJECT" ] || [ "$(echo "$PROJECT" | jq -r 'has("id")' 2>/dev/null)" != "true" ]; then
  echo "Error: could not fetch GitLab project ${PROJECT_PATH}." >&2
  exit 1
fi

DEFAULT_BRANCH=$(echo "$PROJECT" | jq -r '.default_branch // empty')
VISIBILITY=$(echo "$PROJECT" | jq -r '.visibility // empty')
TOPICS=$(echo "$PROJECT" | jq -c '.topics // .tag_list // []')
MERGE_METHOD=$(echo "$PROJECT" | jq -r '.merge_method // "merge"')
SQUASH_OPTION=$(echo "$PROJECT" | jq -r '.squash_option // "default_off"')

# Map GitLab's single merge_method (+ squash option) onto GitHub's three
# independent booleans so the shared vcs policy applies unchanged:
#   merge        -> merge commit          -> allow_merge_commit
#   rebase_merge -> semi-linear history   -> allow_rebase_merge
#   ff           -> fast-forward only     -> (neither merge nor rebase commit)
#   squash_option != "never"              -> allow_squash_merge
if [ "$MERGE_METHOD" = "merge" ]; then ALLOW_MERGE_COMMIT=true; else ALLOW_MERGE_COMMIT=false; fi
if [ "$MERGE_METHOD" = "rebase_merge" ]; then ALLOW_REBASE_MERGE=true; else ALLOW_REBASE_MERGE=false; fi
if [ "$SQUASH_OPTION" = "never" ]; then ALLOW_SQUASH_MERGE=false; else ALLOW_SQUASH_MERGE=true; fi

lunar collect ".vcs.provider" "gitlab" \
      ".vcs.default_branch" "$DEFAULT_BRANCH" \
      ".vcs.visibility" "$VISIBILITY"

echo "$TOPICS" | lunar collect -j ".vcs.topics" -

lunar collect -j \
      ".vcs.merge_strategies.allow_merge_commit" "$ALLOW_MERGE_COMMIT" \
      ".vcs.merge_strategies.allow_squash_merge" "$ALLOW_SQUASH_MERGE" \
      ".vcs.merge_strategies.allow_rebase_merge" "$ALLOW_REBASE_MERGE"
