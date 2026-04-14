#!/bin/bash

set -e

echo "[DEBUG] branch_protection.sh starting" >&2
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

# Get the default branch from the repository
echo "[DEBUG] Fetching repo data for ${OWNER}/${REPO}" >&2
REPO_DATA=$(gh_api "/repos/${OWNER}/${REPO}")
DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')
echo "[DEBUG] Default branch: $DEFAULT_BRANCH" >&2

# Fetch branch protection settings
echo "[DEBUG] Fetching branch protection for branch '$DEFAULT_BRANCH'" >&2
PROTECTION_DATA=$(gh_api "/repos/${OWNER}/${REPO}/branches/${DEFAULT_BRANCH}/protection" 2>/dev/null || echo '{}')
echo "[DEBUG] Protection response length: ${#PROTECTION_DATA}" >&2
echo "[DEBUG] Protection message: $(echo "$PROTECTION_DATA" | jq -r '.message // "none"')" >&2

# Check if branch protection is enabled
if echo "$PROTECTION_DATA" | jq -e '.message == "Branch not protected"' > /dev/null 2>&1 || \
   echo "$PROTECTION_DATA" | jq -e 'has("message") and .message != null' > /dev/null 2>&1; then
  echo "[DEBUG] Branch protection not enabled, collecting minimal data" >&2
  lunar collect -j ".vcs.branch_protection.enabled" false
  lunar collect ".vcs.branch_protection.branch" "$DEFAULT_BRANCH"
  echo "[DEBUG] branch_protection.sh completed (not protected)" >&2
  exit 0
fi

echo "[DEBUG] Branch protection IS enabled, extracting details..." >&2

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
echo "[DEBUG] PR: require=$REQUIRE_PR approvals=$REQUIRED_APPROVALS codeowner=$REQUIRE_CODEOWNER_REVIEW stale=$DISMISS_STALE_REVIEWS" >&2

# Status checks
REQUIRE_STATUS_CHECKS=$(echo "$PROTECTION_DATA" | jq 'has("required_status_checks") and .required_status_checks != null')
if [ "$REQUIRE_STATUS_CHECKS" = "true" ]; then
  REQUIRED_CHECKS=$(echo "$PROTECTION_DATA" | jq -c '.required_status_checks.contexts // []')
  REQUIRE_BRANCHES_UP_TO_DATE=$(echo "$PROTECTION_DATA" | jq '.required_status_checks.strict // false')
else
  REQUIRED_CHECKS='[]'
  REQUIRE_BRANCHES_UP_TO_DATE=false
fi
echo "[DEBUG] Status checks: require=$REQUIRE_STATUS_CHECKS checks=$REQUIRED_CHECKS up_to_date=$REQUIRE_BRANCHES_UP_TO_DATE" >&2

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

echo "[DEBUG] Collecting branch protection data..." >&2
# Collect branch protection data using dot notation
lunar collect -j ".vcs.branch_protection.enabled" true \
      ".vcs.branch_protection.require_pr" "$REQUIRE_PR" \
      ".vcs.branch_protection.required_approvals" "$REQUIRED_APPROVALS" \
      ".vcs.branch_protection.require_codeowner_review" "$REQUIRE_CODEOWNER_REVIEW" \
      ".vcs.branch_protection.dismiss_stale_reviews" "$DISMISS_STALE_REVIEWS" \
      ".vcs.branch_protection.require_status_checks" "$REQUIRE_STATUS_CHECKS" \
      ".vcs.branch_protection.require_branches_up_to_date" "$REQUIRE_BRANCHES_UP_TO_DATE" \
      ".vcs.branch_protection.allow_force_push" "$ALLOW_FORCE_PUSH" \
      ".vcs.branch_protection.allow_deletions" "$ALLOW_DELETIONS" \
      ".vcs.branch_protection.require_linear_history" "$REQUIRE_LINEAR_HISTORY" \
      ".vcs.branch_protection.require_signed_commits" "$REQUIRE_SIGNED_COMMITS"

lunar collect ".vcs.branch_protection.branch" "$DEFAULT_BRANCH"

echo "$RESTRICTIONS_USERS" | lunar collect -j ".vcs.branch_protection.restrictions.users" -
echo "$RESTRICTIONS_TEAMS" | lunar collect -j ".vcs.branch_protection.restrictions.teams" -
echo "$RESTRICTIONS_APPS" | lunar collect -j ".vcs.branch_protection.restrictions.apps" -
echo "$REQUIRED_CHECKS" | lunar collect -j ".vcs.branch_protection.required_checks" -

echo "[DEBUG] branch_protection.sh completed successfully" >&2
