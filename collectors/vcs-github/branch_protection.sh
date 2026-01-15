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

# First, get the default branch if we need it
if [ -z "$LUNAR_VAR_DEFAULT_BRANCH" ]; then
  REPO_DATA=$(gh_api "/repos/${OWNER}/${REPO}")
  DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')
else
  DEFAULT_BRANCH="$LUNAR_VAR_DEFAULT_BRANCH"
fi

BRANCH_TO_CHECK="$DEFAULT_BRANCH"

# Fetch branch protection settings
# Note: This endpoint returns 404 if branch protection is not enabled
PROTECTION_DATA=$(gh_api "/repos/${OWNER}/${REPO}/branches/${BRANCH_TO_CHECK}/protection" 2>/dev/null || echo '{}')

# Check if branch protection is enabled
if echo "$PROTECTION_DATA" | jq -e '.message == "Branch not protected"' > /dev/null 2>&1 || \
   echo "$PROTECTION_DATA" | jq -e 'has("message") and .message != null' > /dev/null 2>&1; then
  # Collect minimal branch protection data
  lunar collect -j ".vcs.branch_protection.enabled" false
  lunar collect ".vcs.branch_protection.branch" "$BRANCH_TO_CHECK"
  exit 0
fi

# Extract branch protection details
REQUIRE_PR=$(echo "$PROTECTION_DATA" | jq 'has("required_pull_request_reviews")')

if [ "$REQUIRE_PR" = "true" ]; then
  REQUIRED_APPROVALS=$(echo "$PROTECTION_DATA" | jq '.required_pull_request_reviews.required_approving_review_count // 0')
  REQUIRE_CODEOWNER_REVIEW=$(echo "$PROTECTION_DATA" | jq '.required_pull_request_reviews.require_code_owner_reviews // false')
  DISMISS_STALE_REVIEWS=$(echo "$PROTECTION_DATA" | jq '.required_pull_request_reviews.dismiss_stale_reviews // false')
else
  REQUIRED_APPROVALS=0
  REQUIRE_CODEOWNER_REVIEW=false
  DISMISS_STALE_REVIEWS=false
fi

# Status checks
REQUIRE_STATUS_CHECKS=$(echo "$PROTECTION_DATA" | jq 'has("required_status_checks") and .required_status_checks != null')
if [ "$REQUIRE_STATUS_CHECKS" = "true" ]; then
  REQUIRED_CHECKS=$(echo "$PROTECTION_DATA" | jq -c '.required_status_checks.contexts // []')
  REQUIRE_BRANCHES_UP_TO_DATE=$(echo "$PROTECTION_DATA" | jq '.required_status_checks.strict // false')
else
  REQUIRED_CHECKS='[]'
  REQUIRE_BRANCHES_UP_TO_DATE=false
fi

# Force push and deletion restrictions
ALLOW_FORCE_PUSH=$(echo "$PROTECTION_DATA" | jq '.allow_force_pushes.enabled // false')
ALLOW_DELETIONS=$(echo "$PROTECTION_DATA" | jq '.allow_deletions.enabled // false')

# Linear history and signed commits
REQUIRE_LINEAR_HISTORY=$(echo "$PROTECTION_DATA" | jq '.required_linear_history.enabled // false')
REQUIRE_SIGNED_COMMITS=$(echo "$PROTECTION_DATA" | jq '.required_signatures.enabled // false')

# Push restrictions (who can push)
RESTRICTIONS_EXIST=$(echo "$PROTECTION_DATA" | jq 'has("restrictions") and .restrictions != null')
if [ "$RESTRICTIONS_EXIST" = "true" ]; then
  RESTRICTIONS_USERS=$(echo "$PROTECTION_DATA" | jq -c '[.restrictions.users[]?.login] // []')
  RESTRICTIONS_TEAMS=$(echo "$PROTECTION_DATA" | jq -c '[.restrictions.teams[]?.slug] // []')
  RESTRICTIONS_APPS=$(echo "$PROTECTION_DATA" | jq -c '[.restrictions.apps[]?.slug] // []')
else
  RESTRICTIONS_USERS='[]'
  RESTRICTIONS_TEAMS='[]'
  RESTRICTIONS_APPS='[]'
fi

# Collect branch protection data using dot notation
lunar collect -j ".vcs.branch_protection.enabled" true
lunar collect ".vcs.branch_protection.branch" "$BRANCH_TO_CHECK"
lunar collect -j ".vcs.branch_protection.require_pr" "$REQUIRE_PR"
lunar collect -j ".vcs.branch_protection.required_approvals" "$REQUIRED_APPROVALS"
lunar collect -j ".vcs.branch_protection.require_codeowner_review" "$REQUIRE_CODEOWNER_REVIEW"
lunar collect -j ".vcs.branch_protection.dismiss_stale_reviews" "$DISMISS_STALE_REVIEWS"
lunar collect -j ".vcs.branch_protection.require_status_checks" "$REQUIRE_STATUS_CHECKS"
echo "$REQUIRED_CHECKS" | lunar collect -j ".vcs.branch_protection.required_checks" -
lunar collect -j ".vcs.branch_protection.require_branches_up_to_date" "$REQUIRE_BRANCHES_UP_TO_DATE"
lunar collect -j ".vcs.branch_protection.allow_force_push" "$ALLOW_FORCE_PUSH"
lunar collect -j ".vcs.branch_protection.allow_deletions" "$ALLOW_DELETIONS"
lunar collect -j ".vcs.branch_protection.require_linear_history" "$REQUIRE_LINEAR_HISTORY"
lunar collect -j ".vcs.branch_protection.require_signed_commits" "$REQUIRE_SIGNED_COMMITS"
echo "$RESTRICTIONS_USERS" | lunar collect -j ".vcs.branch_protection.restrictions.users" -
echo "$RESTRICTIONS_TEAMS" | lunar collect -j ".vcs.branch_protection.restrictions.teams" -
echo "$RESTRICTIONS_APPS" | lunar collect -j ".vcs.branch_protection.restrictions.apps" -
