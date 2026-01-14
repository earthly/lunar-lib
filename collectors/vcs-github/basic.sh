#!/bin/bash

set -e

# Check if we're in GitHub context
if [ "$LUNAR_CI" != "github" ]; then
  echo "Skipping: Not in GitHub CI environment (LUNAR_CI=$LUNAR_CI)"
  exit 0
fi

# Check for required environment variables
if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
  echo "Error: LUNAR_SECRET_GH_TOKEN is not set"
  exit 1
fi

if [ -z "$LUNAR_COMPONENT_ID" ]; then
  echo "Error: LUNAR_COMPONENT_ID is not set"
  exit 1
fi

# LUNAR_COMPONENT_ID should be in format "github.com/owner/repo"
# Extract owner and repo from LUNAR_COMPONENT_ID
OWNER=$(echo "$LUNAR_COMPONENT_ID" | cut -d'/' -f2)
REPO=$(echo "$LUNAR_COMPONENT_ID" | cut -d'/' -f3)

if [ -z "$OWNER" ] || [ -z "$REPO" ]; then
  echo "Error: Could not parse LUNAR_COMPONENT_ID='$LUNAR_COMPONENT_ID' (expected format: github.com/owner/repo)"
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

echo "Fetching basic repository settings for $REPO_FULL_NAME..."

# Fetch repository information
REPO_DATA=$(gh_api "/repos/${OWNER}/${REPO}")

# Extract basic repository settings
DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')
VISIBILITY=$(echo "$REPO_DATA" | jq -r '.visibility')
TOPICS=$(echo "$REPO_DATA" | jq -c '.topics // []')
ALLOW_MERGE_COMMIT=$(echo "$REPO_DATA" | jq '.allow_merge_commit')
ALLOW_SQUASH_MERGE=$(echo "$REPO_DATA" | jq '.allow_squash_merge')
ALLOW_REBASE_MERGE=$(echo "$REPO_DATA" | jq '.allow_rebase_merge')

echo "Repository settings collected:"
echo "  Default branch: $DEFAULT_BRANCH"
echo "  Visibility: $VISIBILITY"
echo "  Topics: $TOPICS"
echo "  Merge strategies: merge=$ALLOW_MERGE_COMMIT, squash=$ALLOW_SQUASH_MERGE, rebase=$ALLOW_REBASE_MERGE"

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

echo "Basic GitHub repository settings collected successfully"
