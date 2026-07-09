#!/bin/bash
#
# Backstage catalog-info Cataloger — SCHEDULED variant (component-cron).
#
# Runs once per existing component on a schedule. Fetches `catalog-info.yaml`
# (or `.yml`) from the component's GitHub repo via the Contents API, then hands
# the file to the shared augment pipeline in `helpers.sh`, which parses it,
# picks the matching `Component` entity, and writes a single
# `.components["$LUNAR_COMPONENT_ID"]` entry (plus a `.domains` stub) into the
# Catalog JSON.
#
# The commit-triggered sibling `main-on-commit.sh` shares the same pipeline —
# only the acquisition step (this file's GitHub fetch vs. reading the checkout)
# differs. Keep augmentation logic in `helpers.sh`, not here.
#
# Silent skips (exit 0 with a log line, no write):
#   - Component ID is not a github.com/<owner>/<repo>
#   - No catalog-info.yaml at any of the configured paths (404 from GH)
#   - YAML parse error / no matching Component (handled in helpers.sh)
#
# Inputs (LUNAR_VAR_*):
#   paths                    (default catalog-info.yaml,catalog-info.yml)
#   branch                   (default empty → repo's default branch)
#   component_id_prefix      (default github.com/) — used here to parse the ID
#   ...matcher/transform inputs are read in helpers.sh
#
# Secrets:
#   GH_TOKEN — required, fetched as LUNAR_SECRET_GH_TOKEN

set -euo pipefail

COMPONENT_ID="${LUNAR_COMPONENT_ID:?LUNAR_COMPONENT_ID must be set by the component-cron runner}"

PATHS="${LUNAR_VAR_PATHS:-catalog-info.yaml,catalog-info.yml}"
BRANCH="${LUNAR_VAR_BRANCH:-}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"

if [ -n "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
    export GH_TOKEN="$LUNAR_SECRET_GH_TOKEN"
elif [ -z "${GH_TOKEN:-}" ]; then
    echo "GH_TOKEN or LUNAR_SECRET_GH_TOKEN must be set" >&2
    exit 1
fi

echo "Component: $COMPONENT_ID"
echo "Paths: $PATHS"
[ -n "$BRANCH" ] && echo "Branch: $BRANCH"

# --- Parse component ID into owner/repo -----------------------------------
# Only github.com/<owner>/<repo> IDs are supported. Anything else (gitlab,
# bitbucket, custom schemes) silently skips — the Contents API fetch is
# GitHub-specific. (The commit-triggered variant has no such restriction; it
# reads whatever repo the hook checked out.)

if [[ "$COMPONENT_ID" != "${COMPONENT_ID_PREFIX}"* ]]; then
    echo "Component id '$COMPONENT_ID' does not start with prefix '$COMPONENT_ID_PREFIX' — skipping"
    exit 0
fi
SLUG="${COMPONENT_ID#"$COMPONENT_ID_PREFIX"}"
if [[ "$SLUG" != */* ]]; then
    echo "Component id '$COMPONENT_ID' is not in '$COMPONENT_ID_PREFIX<owner>/<repo>' form — skipping"
    exit 0
fi

# --- Fetch catalog-info.yaml ----------------------------------------------
# Try each configured path in order. First success wins. GitHub Contents API
# returns the raw file body when called with `Accept: application/vnd.github.raw`.
# 404 → silently try the next path. Any other GH error → silent skip.
#
# curl over `gh api` because the lunar-lib base image is `alpine + lunar-scripts`
# (no GitHub CLI). curl is always present; `gh` would require a custom image.

YAML=""
FOUND_PATH=""
ERR_FILE=$(mktemp)
trap 'rm -f "$ERR_FILE" "$ERR_FILE.body"' EXIT

IFS=',' read -ra PATH_ARRAY <<< "$PATHS"
for raw_path in "${PATH_ARRAY[@]}"; do
    path="$(echo "$raw_path" | xargs)"
    [ -z "$path" ] && continue
    URL="https://api.github.com/repos/$SLUG/contents/$path"
    if [ -n "$BRANCH" ]; then
        URL="${URL}?ref=${BRANCH}"
    fi
    HTTP_CODE=$(curl -sS -o "$ERR_FILE.body" -w '%{http_code}' \
        -H "Authorization: Bearer $GH_TOKEN" \
        -H "Accept: application/vnd.github.raw" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$URL" 2>"$ERR_FILE" || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        YAML=$(cat "$ERR_FILE.body")
        FOUND_PATH="$path"
        rm -f "$ERR_FILE.body"
        break
    fi
    # 404 → file absent at this path, try next. Other non-2xx (auth, rate-limit)
    # → surface the response body in logs so the failure is debuggable, but
    # still silently skip overall (per design).
    if [ "$HTTP_CODE" != "404" ]; then
        echo "GH Contents API returned $HTTP_CODE for $URL: $(head -c 200 "$ERR_FILE.body" 2>/dev/null)" >&2
    fi
    rm -f "$ERR_FILE.body"
    YAML=""
done

if [ -z "$YAML" ]; then
    echo "No catalog-info.yaml at any of '$PATHS' in '$SLUG' — skipping"
    exit 0
fi
echo "Fetched $FOUND_PATH from $SLUG (${#YAML} bytes)"

# --- Augment ---------------------------------------------------------------
# Hand the fetched YAML to the shared pipeline (parse → match → transform →
# write). Identical to what main-on-commit.sh does after reading the checkout.

# helpers.sh lives next to this script; resolved at runtime via dirname.
# shellcheck disable=SC1091
source "$(dirname "$0")/helpers.sh"
augment_component "$COMPONENT_ID" "$YAML"
