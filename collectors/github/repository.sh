#!/bin/bash

set -e

# Check for required environment variables
if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
  echo "Error: LUNAR_SECRET_GH_TOKEN is not set" >&2
  exit 1
fi

if [ -z "$LUNAR_COMPONENT_ID" ]; then
  echo "Error: LUNAR_COMPONENT_ID is not set" >&2
  exit 1
fi

# Only process GitHub repositories
if [[ ! "$LUNAR_COMPONENT_ID" =~ ^github\.com/ ]]; then
  echo "Error: LUNAR_COMPONENT_ID must start with github.com (got: $LUNAR_COMPONENT_ID)" >&2
  exit 1
fi

# LUNAR_COMPONENT_ID should be in format "github.com/owner/repo"
# Extract owner and repo from LUNAR_COMPONENT_ID
OWNER=$(echo "$LUNAR_COMPONENT_ID" | cut -d'/' -f2)
REPO=$(echo "$LUNAR_COMPONENT_ID" | cut -d'/' -f3)

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

  curl -sSL -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
       -H "Accept: application/vnd.github+json" \
       -H "X-GitHub-Api-Version: 2022-11-28" \
       "$url"
}

# Fetch repository information
REPO_DATA=$(gh_api "/repos/${OWNER}/${REPO}")

# Extract basic repository settings
DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')
VISIBILITY=$(echo "$REPO_DATA" | jq -r '.visibility')
TOPICS=$(echo "$REPO_DATA" | jq -c '.topics // []')
ALLOW_MERGE_COMMIT=$(echo "$REPO_DATA" | jq '.allow_merge_commit')
ALLOW_SQUASH_MERGE=$(echo "$REPO_DATA" | jq '.allow_squash_merge')
ALLOW_REBASE_MERGE=$(echo "$REPO_DATA" | jq '.allow_rebase_merge')

# Collect provider (string)
lunar collect ".vcs.provider" "github"

# Collect default branch (string)
lunar collect ".vcs.default_branch" "$DEFAULT_BRANCH"

# Collect visibility (string)
lunar collect ".vcs.visibility" "$VISIBILITY"

# Collect topics (array)
echo "$TOPICS" | lunar collect -j ".vcs.topics" -

# Collect merge strategies (booleans)
lunar collect -j ".vcs.merge_strategies.allow_merge_commit" "$ALLOW_MERGE_COMMIT"
lunar collect -j ".vcs.merge_strategies.allow_squash_merge" "$ALLOW_SQUASH_MERGE"
lunar collect -j ".vcs.merge_strategies.allow_rebase_merge" "$ALLOW_REBASE_MERGE"
