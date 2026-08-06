#!/bin/bash

set -e

# Collect GitLab protected-branch + approval configuration for the default
# branch into the shared .vcs.branch_protection shape (source: "gitlab").

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

# GitLab protected-branch access levels: 0=no one, 30=developer, 40=maintainer,
# 60=admin. Map to human-readable names for the restrictions object.
level_name() {
  case "$1" in
    0) echo "no one" ;;
    30) echo "developer" ;;
    40) echo "maintainer" ;;
    60) echo "admin" ;;
    "") echo "" ;;
    *) echo "$1" ;;
  esac
}

PROJECT=$(gl_api "/projects/${PROJECT_ENC}")
if [ -z "$PROJECT" ] || [ "$(echo "$PROJECT" | jq -r 'has("id")' 2>/dev/null)" != "true" ]; then
  echo "Error: could not fetch GitLab project ${PROJECT_PATH}. Aborting so last-known-good data is retained." >&2
  exit 1
fi
DEFAULT_BRANCH=$(echo "$PROJECT" | jq -r '.default_branch // empty')
REQUIRE_STATUS_CHECKS=$(echo "$PROJECT" | jq '.only_allow_merge_if_pipeline_succeeds // false')

PROTECTED=$(gl_api "/projects/${PROJECT_ENC}/protected_branches")
PB=$(echo "$PROTECTED" | jq -c --arg b "$DEFAULT_BRANCH" \
  'if type=="array" then (map(select(.name==$b)) | first) else null end' 2>/dev/null || echo "null")

if [ -z "$PB" ] || [ "$PB" = "null" ]; then
  # Default branch is not protected.
  lunar collect -j ".vcs.branch_protection.enabled" false \
                ".vcs.branch_protection.source" '"gitlab"'
  lunar collect ".vcs.branch_protection.branch" "$DEFAULT_BRANCH"
  exit 0
fi

ALLOW_FORCE_PUSH=$(echo "$PB" | jq '.allow_force_push // false')
REQUIRE_CODEOWNER=$(echo "$PB" | jq '.code_owner_approval_required // false')
PUSH_LEVEL=$(echo "$PB" | jq -r '.push_access_levels[0].access_level // empty')
MERGE_LEVEL=$(echo "$PB" | jq -r '.merge_access_levels[0].access_level // empty')

# Required approvals: prefer the approval_rules endpoint (the real, current
# source on instances that enforce MR approval rules), summing approvals_required
# across rules that apply to the default branch — a rule with no protected_branches
# applies to all branches. Fall back to the deprecated project-level
# approvals_before_merge, then 0. approval_rules 403s on instances without the
# approvals feature licensed, so degrade gracefully.
RULES=$(gl_api "/projects/${PROJECT_ENC}/approval_rules" 2>/dev/null || echo "")
REQUIRED_APPROVALS=""
if echo "$RULES" | jq -e 'type == "array" and length > 0' >/dev/null 2>&1; then
  REQUIRED_APPROVALS=$(echo "$RULES" | jq --arg b "$DEFAULT_BRANCH" '
    [ .[]
      | select(((.protected_branches // []) | length == 0)
               or ((.protected_branches // []) | any(.name == $b)))
      | (.approvals_required // 0) ]
    | add // 0' 2>/dev/null)
fi
if [ -z "$REQUIRED_APPROVALS" ] || [ "$REQUIRED_APPROVALS" = "null" ]; then
  APPROVALS=$(gl_api "/projects/${PROJECT_ENC}/approvals" 2>/dev/null || echo "{}")
  REQUIRED_APPROVALS=$(echo "$APPROVALS" | jq '.approvals_before_merge // 0' 2>/dev/null || echo 0)
fi

# A protected default branch restricts direct pushes, so changes land via MR,
# and GitLab does not allow deleting a protected branch.
lunar collect -j \
      ".vcs.branch_protection.enabled" true \
      ".vcs.branch_protection.source" '"gitlab"' \
      ".vcs.branch_protection.require_pr" true \
      ".vcs.branch_protection.required_approvals" "$REQUIRED_APPROVALS" \
      ".vcs.branch_protection.require_codeowner_review" "$REQUIRE_CODEOWNER" \
      ".vcs.branch_protection.require_status_checks" "$REQUIRE_STATUS_CHECKS" \
      ".vcs.branch_protection.allow_force_push" "$ALLOW_FORCE_PUSH" \
      ".vcs.branch_protection.allow_deletions" false

lunar collect \
      ".vcs.branch_protection.branch" "$DEFAULT_BRANCH" \
      ".vcs.branch_protection.restrictions.push_access_level" "$(level_name "$PUSH_LEVEL")" \
      ".vcs.branch_protection.restrictions.merge_access_level" "$(level_name "$MERGE_LEVEL")"
