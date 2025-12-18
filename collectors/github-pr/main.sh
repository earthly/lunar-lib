#!/bin/bash
set -e

if [ -z "${LUNAR_COMPONENT_PR:-}" ]; then
  # Only run inside PR contexts.
  lunar collect -j ".github.is_pr" false
  echo "Not in a PR"
  exit 0
fi

lunar collect -j ".github.is_pr" true

if [ -z "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
  echo "GitHub PR collector requires LUNAR_SECRET_GH_TOKEN to query GitHub." >&2
  exit 0
fi

if [ -z "${LUNAR_COMPONENT_ID:-}" ]; then
  echo "GitHub PR collector requires LUNAR_COMPONENT_ID to identify the repository." >&2
  exit 0
fi

REPO="${LUNAR_COMPONENT_ID#github.com/}"

set +e
PR_RESPONSE="$(curl -fsS \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: token ${LUNAR_SECRET_GH_TOKEN}" \
  "https://api.github.com/repos/${REPO}/pulls/${LUNAR_COMPONENT_PR}")"
CURL_STATUS=$?
set -e

if [ $CURL_STATUS -ne 0 ] || [ -z "$PR_RESPONSE" ]; then
  echo "Unable to fetch PR ${LUNAR_COMPONENT_PR} metadata from GitHub." >&2
  exit 0
fi

# Collect the entire PR JSON response
echo "$PR_RESPONSE" | lunar collect -j ".github.pr" -
