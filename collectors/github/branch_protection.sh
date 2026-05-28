#!/bin/bash

set -e

# Only process GitHub repositories
if [[ ! "$LUNAR_COMPONENT_ID" =~ ^github\.com/ ]]; then
  echo "Skipping: LUNAR_COMPONENT_ID='${LUNAR_COMPONENT_ID:-<unset>}' is not a GitHub repository" >&2
  exit 0
fi

# Check for required environment variables
if [ -z "$LUNAR_SECRET_GH_TOKEN" ]; then
  echo "Error: LUNAR_SECRET_GH_TOKEN is not set. Configure the GH_TOKEN secret for this collector." >&2
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

# Get the default branch from the repository
REPO_DATA=$(gh_api "/repos/${OWNER}/${REPO}")
DEFAULT_BRANCH=$(echo "$REPO_DATA" | jq -r '.default_branch')

# Fetch classic branch protection settings.
# Returns the protection object on success, or {"message": "Branch not protected", ...} on 404.
PROTECTION_DATA=$(gh_api "/repos/${OWNER}/${REPO}/branches/${DEFAULT_BRANCH}/protection" 2>/dev/null || echo '{}')

CLASSIC_PROTECTED=true
if echo "$PROTECTION_DATA" | jq -e 'has("message") and .message != null' > /dev/null 2>&1; then
  CLASSIC_PROTECTED=false
fi

if [ "$CLASSIC_PROTECTED" = "true" ]; then
  # ---- Classic branch protection path (preserves pre-rulesets output) ----
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

  REQUIRE_STATUS_CHECKS=$(echo "$PROTECTION_DATA" | jq 'has("required_status_checks") and .required_status_checks != null')
  if [ "$REQUIRE_STATUS_CHECKS" = "true" ]; then
    REQUIRED_CHECKS=$(echo "$PROTECTION_DATA" | jq -c '.required_status_checks.contexts // []')
    REQUIRE_BRANCHES_UP_TO_DATE=$(echo "$PROTECTION_DATA" | jq '.required_status_checks.strict // false')
  else
    REQUIRED_CHECKS='[]'
    REQUIRE_BRANCHES_UP_TO_DATE=false
  fi

  ALLOW_FORCE_PUSH=$(echo "$PROTECTION_DATA" | jq '.allow_force_pushes.enabled // false')
  ALLOW_DELETIONS=$(echo "$PROTECTION_DATA" | jq '.allow_deletions.enabled // false')

  REQUIRE_LINEAR_HISTORY=$(echo "$PROTECTION_DATA" | jq '.required_linear_history.enabled // false')
  REQUIRE_SIGNED_COMMITS=$(echo "$PROTECTION_DATA" | jq '.required_signatures.enabled // false')

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

  SOURCE="classic"
else
  # ---- Rulesets fallback ----
  # GitHub now recommends rulesets over classic branch protection. A repo can be
  # fully protected via a ruleset and still 404 on the classic endpoint above.
  # Query the effective-rules endpoint to detect ruleset-based protection.
  RULES_DATA=$(gh_api "/repos/${OWNER}/${REPO}/rules/branches/${DEFAULT_BRANCH}" 2>/dev/null || echo '[]')

  # Error responses come back as objects ({"message": "..."}) — coerce anything
  # that isn't an array to empty.
  if ! echo "$RULES_DATA" | jq -e 'type == "array"' > /dev/null 2>&1; then
    RULES_DATA='[]'
  fi

  if [ "$(echo "$RULES_DATA" | jq 'length')" = "0" ]; then
    # No classic protection AND no rulesets — truly unprotected.
    lunar collect -j ".vcs.branch_protection.enabled" false \
                  ".vcs.branch_protection.source" '"none"'
    lunar collect ".vcs.branch_protection.branch" "$DEFAULT_BRANCH"
    exit 0
  fi

  # Derive each branch_protection field from the matching rule type. Field
  # names in the wire format differ from classic protection (e.g.
  # dismiss_stale_reviews_on_push vs dismiss_stale_reviews); the output schema
  # mirrors the classic-path names so consuming policies don't need to branch.
  #
  # /rules/branches/{branch} returns one entry per rule per ruleset, so when an
  # org-level and a repo-level ruleset both target this branch we get multiple
  # entries of the same type. GitHub enforces the most restrictive across them,
  # so we aggregate: max() for numeric counts, any-true for booleans, and
  # union+dedup for context lists.
  PR_RULES=$(echo "$RULES_DATA" | jq -c '[.[] | select(.type == "pull_request")]')
  if [ "$(echo "$PR_RULES" | jq 'length')" = "0" ]; then
    REQUIRE_PR=false
    REQUIRED_APPROVALS=0
    REQUIRE_CODEOWNER_REVIEW=false
    DISMISS_STALE_REVIEWS=false
  else
    REQUIRE_PR=true
    REQUIRED_APPROVALS=$(echo "$PR_RULES" | jq '[.[].parameters.required_approving_review_count // 0] | max')
    REQUIRE_CODEOWNER_REVIEW=$(echo "$PR_RULES" | jq 'any(.[]; .parameters.require_code_owner_review // false)')
    DISMISS_STALE_REVIEWS=$(echo "$PR_RULES" | jq 'any(.[]; .parameters.dismiss_stale_reviews_on_push // false)')
  fi

  STATUS_CHECKS_RULES=$(echo "$RULES_DATA" | jq -c '[.[] | select(.type == "required_status_checks")]')
  if [ "$(echo "$STATUS_CHECKS_RULES" | jq 'length')" = "0" ]; then
    REQUIRE_STATUS_CHECKS=false
    REQUIRED_CHECKS='[]'
    REQUIRE_BRANCHES_UP_TO_DATE=false
  else
    REQUIRE_STATUS_CHECKS=true
    REQUIRED_CHECKS=$(echo "$STATUS_CHECKS_RULES" | jq -c '[.[].parameters.required_status_checks[]?.context] | unique')
    REQUIRE_BRANCHES_UP_TO_DATE=$(echo "$STATUS_CHECKS_RULES" | jq 'any(.[]; .parameters.strict_required_status_checks_policy // false)')
  fi

  # non_fast_forward rule blocks force-push; absent => allowed
  if [ "$(echo "$RULES_DATA" | jq 'any(.[]; .type == "non_fast_forward")')" = "true" ]; then
    ALLOW_FORCE_PUSH=false
  else
    ALLOW_FORCE_PUSH=true
  fi

  # deletion rule blocks branch deletion; absent => allowed
  if [ "$(echo "$RULES_DATA" | jq 'any(.[]; .type == "deletion")')" = "true" ]; then
    ALLOW_DELETIONS=false
  else
    ALLOW_DELETIONS=true
  fi

  REQUIRE_LINEAR_HISTORY=$(echo "$RULES_DATA" | jq 'any(.[]; .type == "required_linear_history")')
  REQUIRE_SIGNED_COMMITS=$(echo "$RULES_DATA" | jq 'any(.[]; .type == "required_signatures")')

  # Rulesets use bypass_actors rather than push restrictions — different
  # semantics, not surfaced here. Leave the restrictions arrays empty.
  RESTRICTIONS_USERS='[]'
  RESTRICTIONS_TEAMS='[]'
  RESTRICTIONS_APPS='[]'

  SOURCE="ruleset"
fi

# Collect branch protection data using dot notation
lunar collect -j ".vcs.branch_protection.enabled" true \
      ".vcs.branch_protection.source" "\"${SOURCE}\"" \
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
