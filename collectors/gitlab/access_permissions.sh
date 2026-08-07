#!/bin/bash

set -e

# Collect GitLab project members and shared groups into .vcs.access.

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

# Fetch a paginated list endpoint, concatenating all pages into one JSON array.
gl_api_paginated() {
  local endpoint="$1"
  local all_data="[]"
  local page=1
  while true; do
    local response
    response=$(curl -sSL -H "PRIVATE-TOKEN: ${LUNAR_SECRET_GL_TOKEN}" \
      "${API_BASE}${endpoint}?per_page=100&page=${page}")
    local item_count
    item_count=$(echo "$response" | jq 'if type == "array" then length else 0 end' 2>/dev/null || echo 0)
    if [ "$item_count" -eq 0 ]; then
      break
    fi
    all_data=$(echo "$all_data" | jq --argjson new "$response" '. + $new')
    if [ "$item_count" -lt 100 ]; then
      break
    fi
    page=$((page + 1))
  done
  echo "$all_data"
}

# GitLab member/group access levels: 10=guest, 20=reporter, 30=developer,
# 40=maintainer, 50=owner. Normalize to names, mirroring the github collector.
LEVEL_MAP='def lvl: if .==50 then "owner" elif .==40 then "maintainer" elif .==30 then "developer" elif .==20 then "reporter" elif .==10 then "guest" else "none" end;'

# Direct + inherited project members.
MEMBERS_DATA=$(gl_api_paginated "/projects/${PROJECT_ENC}/members/all")
COLLABORATORS=$(echo "$MEMBERS_DATA" | jq "${LEVEL_MAP}"'[.[] | {username: .username, permission: (.access_level | lvl), type: "User"}]')

# Groups the project is shared with (returned inline on the project object).
PROJECT=$(curl -sSL -H "PRIVATE-TOKEN: ${LUNAR_SECRET_GL_TOKEN}" "${API_BASE}/projects/${PROJECT_ENC}")
TEAMS=$(echo "$PROJECT" | jq "${LEVEL_MAP}"'[.shared_with_groups[]? | {slug: .group_full_path, name: .group_name, permission: (.group_access_level | lvl)}]')

echo "$COLLABORATORS" | lunar collect -j ".vcs.access.collaborators" -
echo "$TEAMS" | lunar collect -j ".vcs.access.teams" -
