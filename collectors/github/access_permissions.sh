#!/bin/bash

set -e

echo "[DEBUG] access_permissions.sh starting" >&2
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

# Helper function to call GitHub API with pagination support
gh_api() {
  local endpoint="$1"
  local url="${API_BASE}${endpoint}"
  local all_data="[]"
  local page=1

  echo "[DEBUG] gh_api (paginated): starting GET $url" >&2

  while true; do
    local full_url="${url}?per_page=100&page=${page}"
    echo "[DEBUG] gh_api: GET $full_url" >&2

    local response
    local http_code
    response=$(curl -sSL -w "\n%{http_code}" -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
         -H "Accept: application/vnd.github+json" \
         -H "X-GitHub-Api-Version: 2022-11-28" \
         "$full_url")
    http_code=$(echo "$response" | tail -1)
    response=$(echo "$response" | sed '$d')
    echo "[DEBUG] gh_api: HTTP $http_code (response length: ${#response})" >&2

    if [ "$http_code" -ge 400 ] 2>/dev/null; then
      echo "[DEBUG] gh_api: ERROR response: $(echo "$response" | head -c 500)" >&2
      break
    fi

    # Check if response is an array and not empty
    local item_count=$(echo "$response" | jq 'if type == "array" then length else 0 end')
    echo "[DEBUG] gh_api: page $page returned $item_count items" >&2

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

  echo "[DEBUG] gh_api: total items collected: $(echo "$all_data" | jq length)" >&2
  echo "$all_data"
}

echo "[DEBUG] Fetching collaborators for ${OWNER}/${REPO}" >&2
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
echo "[DEBUG] Parsed $(echo "$COLLABORATORS" | jq length) collaborators" >&2

echo "[DEBUG] Fetching teams for ${OWNER}/${REPO}" >&2
TEAMS_DATA=$(gh_api "/repos/${OWNER}/${REPO}/teams")

# Extract team information (slug and permission)
TEAMS=$(echo "$TEAMS_DATA" | jq '[.[] | {
  slug: .slug,
  name: .name,
  permission: .permission
}]')
echo "[DEBUG] Parsed $(echo "$TEAMS" | jq length) teams" >&2

echo "[DEBUG] Collecting access permissions data..." >&2
echo "$COLLABORATORS" | lunar collect -j ".vcs.access.collaborators" -
echo "$TEAMS" | lunar collect -j ".vcs.access.teams" -

echo "[DEBUG] access_permissions.sh completed successfully" >&2
