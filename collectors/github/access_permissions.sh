#!/bin/bash

set -e

# Only process GitHub repositories
if [[ ! "$LUNAR_COMPONENT_ID" =~ ^github\.com/ ]]; then
  echo "Skipping: LUNAR_COMPONENT_ID='${LUNAR_COMPONENT_ID:-<unset>}' is not a GitHub repository" >&2
  exit 0
fi

# With github_app set, mint a token from that Hub GitHub App (`lunar github-app add`)
# instead of using the GH_TOKEN secret. The token asks for only the permissions this
# script uses, so an App without them falls back; github_app_only turns that off.
if [ -n "${LUNAR_VAR_GITHUB_APP:-}" ] && APP_TOKEN=$(lunar github-app get-token "$LUNAR_VAR_GITHUB_APP" --permission metadata=read --permission administration=read) \
    && [ -n "$APP_TOKEN" ]; then
  echo "GitHub auth: GitHub App $LUNAR_VAR_GITHUB_APP" >&2
  export LUNAR_SECRET_GH_TOKEN="$APP_TOKEN"
elif [ "${LUNAR_VAR_GITHUB_APP_ONLY:-false}" = "true" ]; then
  echo "GitHub auth: no token from GitHub App ${LUNAR_VAR_GITHUB_APP:-(github_app is not set)}, and github_app_only is set" >&2
  exit 1
elif [ -n "${LUNAR_VAR_GITHUB_APP:-}" ]; then
  echo "GitHub auth: GH_TOKEN secret, because GitHub App $LUNAR_VAR_GITHUB_APP minted no token" >&2
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

# Helper function to call GitHub API with pagination support
gh_api() {
  local endpoint="$1"
  local url="${API_BASE}${endpoint}"
  local all_data="[]"
  local page=1

  while true; do
    local response=$(curl -sSL -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
         -H "Accept: application/vnd.github+json" \
         -H "X-GitHub-Api-Version: 2022-11-28" \
         "${url}?per_page=100&page=${page}")

    # Check if response is an array and not empty
    local item_count=$(echo "$response" | jq 'if type == "array" then length else 0 end')

    if [ "$item_count" -eq 0 ]; then
      break
    fi

    all_data=$(echo "$all_data" | jq --argjson new "$response" '. + $new')

    # If we got less than 100 items, we're done
    if [ "$item_count" -lt 100 ]; then
      break
    fi

    page=$((page + 1))
  done

  echo "$all_data"
}

# Fetch direct collaborators
COLLABORATORS_DATA=$(gh_api "/repos/${OWNER}/${REPO}/collaborators")

# Extract collaborator information (login and permissions)
COLLABORATORS=$(echo "$COLLABORATORS_DATA" | jq '[.[] | {
  login: .login,
  permission: .permissions |
    if .admin then "admin"
    elif .maintain then "maintain"
    elif .push then "write"
    elif .triage then "triage"
    elif .pull then "read"
    else "none"
    end,
  type: .type
}]')

# Fetch teams with access
TEAMS_DATA=$(gh_api "/repos/${OWNER}/${REPO}/teams")

# Extract team information (slug and permission)
TEAMS=$(echo "$TEAMS_DATA" | jq '[.[] | {
  slug: .slug,
  name: .name,
  permission: .permission
}]')

# Collect access permissions using dot notation
echo "$COLLABORATORS" | lunar collect -j ".vcs.access.collaborators" -
echo "$TEAMS" | lunar collect -j ".vcs.access.teams" -
