#!/bin/bash

set -e

echo "[DEBUG] repository.sh starting" >&2
echo "[DEBUG] LUNAR_COMPONENT_ID=${LUNAR_COMPONENT_ID:-<unset>}" >&2
echo "[DEBUG] LUNAR_SECRET_GH_TOKEN set: $([ -n "$LUNAR_SECRET_GH_TOKEN" ] && echo 'yes' || echo 'no')" >&2
echo "[DEBUG] LUNAR_SECRET_GH_TOKEN length: ${#LUNAR_SECRET_GH_TOKEN}" >&2

# Only process GitHub repositories
if [[ ! "$LUNAR_COMPONENT_ID" =~ ^github\.com/ ]]; then
  echo "[DEBUG] LUNAR_COMPONENT_ID does not match ^github.com/ — exiting 0" >&2
  exit 0
fi
echo "[DEBUG] Component ID matches github.com pattern" >&2

# Check for required environment variables
if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
  echo "[DEBUG] LUNAR_SECRET_GH_TOKEN is empty — exiting 1" >&2
  echo "Error: LUNAR_SECRET_GH_TOKEN is not set" >&2
  exit 1
fi

if [ -z "$LUNAR_COMPONENT_ID" ]; then
  echo "[DEBUG] LUNAR_COMPONENT_ID is empty — exiting 1" >&2
  echo "Error: LUNAR_COMPONENT_ID is not set" >&2
  exit 1
fi

# LUNAR_COMPONENT_ID should be in format "github.com/owner/repo"
# Extract owner and repo from LUNAR_COMPONENT_ID
OWNER=$(echo "$LUNAR_COMPONENT_ID" | cut -d'/' -f2)
REPO=$(echo "$LUNAR_COMPONENT_ID" | cut -d'/' -f3)
echo "[DEBUG] Parsed OWNER=$OWNER REPO=$REPO" >&2

if [ -z "$OWNER" ] || [ -z "$REPO" ]; then
  echo "Error: Could not parse LUNAR_COMPONENT_ID='$LUNAR_COMPONENT_ID' (expected format: github.com/owner/repo)" >&2
  exit 1
fi

REPO_FULL_NAME="${OWNER}/${REPO}"

# GitHub API base URL
API_BASE="https://api.github.com"

# Helper function to call GitHub API
gh_api() {
  local endpoint="$1"
  local url="${API_BASE}${endpoint}"
  echo "[DEBUG] gh_api: GET $url" >&2

  local http_code
  local response
  response=$(curl -sSL -w "\n%{http_code}" -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
       -H "Accept: application/vnd.github+json" \
       -H "X-GitHub-Api-Version: 2022-11-28" \
       "$url")
  http_code=$(echo "$response" | tail -1)
  response=$(echo "$response" | sed '$d')
  echo "[DEBUG] gh_api: HTTP $http_code (response length: ${#response})" >&2

  if [ "$http_code" -ge 400 ] 2>/dev/null; then
    echo "[DEBUG] gh_api: ERROR response: $(echo "$response" | head -c 500)" >&2
  fi

  echo "$response"
}

echo "[DEBUG] Fetching repo data for ${OWNER}/${REPO}" >&2
REPO_DATA=$(gh_api "/repos/${OWNER}/${REPO}")

# Extract basic repository settings
DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')
VISIBILITY=$(echo "$REPO_DATA" | jq -r '.visibility')
TOPICS=$(echo "$REPO_DATA" | jq -c '.topics // []')
ALLOW_MERGE_COMMIT=$(echo "$REPO_DATA" | jq '.allow_merge_commit')
ALLOW_SQUASH_MERGE=$(echo "$REPO_DATA" | jq '.allow_squash_merge')
ALLOW_REBASE_MERGE=$(echo "$REPO_DATA" | jq '.allow_rebase_merge')

echo "[DEBUG] Parsed: default_branch=$DEFAULT_BRANCH visibility=$VISIBILITY topics=$TOPICS" >&2
echo "[DEBUG] Merge strategies: commit=$ALLOW_MERGE_COMMIT squash=$ALLOW_SQUASH_MERGE rebase=$ALLOW_REBASE_MERGE" >&2

echo "[DEBUG] Collecting VCS data..." >&2
# Collect provider (string)
lunar collect ".vcs.provider" "github" \
      ".vcs.default_branch" "$DEFAULT_BRANCH" \
      ".vcs.visibility" "$VISIBILITY"

# Collect topics (array)
echo "$TOPICS" | lunar collect -j ".vcs.topics" -

# Collect merge strategies (booleans)
lunar collect -j \
      ".vcs.merge_strategies.allow_merge_commit" "$ALLOW_MERGE_COMMIT" \
      ".vcs.merge_strategies.allow_squash_merge" "$ALLOW_SQUASH_MERGE" \
      ".vcs.merge_strategies.allow_rebase_merge" "$ALLOW_REBASE_MERGE"

echo "[DEBUG] repository.sh completed successfully" >&2
