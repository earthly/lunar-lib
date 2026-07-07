#!/bin/bash
#
# Backstage catalog-info Monorepo Discovery Cataloger — SCHEDULED variant (cron).
#
# Runs once per cron tick (global, no repo checkout). For each repo in the
# `repos` input, walks the whole file tree via the GitHub Git Trees API (one
# recursive call), finds every `catalog-info.yaml` / `.yml` (including files in
# subdirectories), fetches each via the Contents API, and CREATES one component
# per discovered file — keyed to the file's directory so a monorepo becomes one
# component per service. Owner / domain / tags come from the file's `Component`
# entity via the shared pipeline in `helpers.sh`.
#
# Component id per file (with default component_id_prefix `github.com/`):
#   catalog-info.yaml (repo root)          -> github.com/<owner>/<repo>
#   services/payments/catalog-info.yaml    -> github.com/<owner>/<repo>/services/payments
#
# By default (`skip_root_file=true`) a root catalog-info.yaml is ignored — the
# augment `backstage-catalog-info` cataloger owns the repo-level component — and
# only subdirectory files become (sub)components. Set skip_root_file=false to
# also map a root file to the repo-level id (standalone use).
#
# Silent skips (exit 0 with a log line, no write):
#   - No GH_TOKEN, or empty `repos` input (nothing to do)
#   - A repo id that isn't `<owner>/<repo>`
#   - Git Trees / Contents API errors for a repo (logged, repo skipped)
#   - Per-file: parse error / not exactly one Component (handled in helpers.sh)
#
# Inputs (LUNAR_VAR_*):
#   repos                (required; comma-separated <owner>/<repo>)
#   filenames            (default catalog-info.yaml,catalog-info.yml)
#   branch               (default empty -> each repo's default branch)
#   skip_root_file       (default true)
#   component_id_prefix  (default github.com/)
#   ...transform inputs are read in helpers.sh
#
# Secrets:
#   GH_TOKEN — required, fetched as LUNAR_SECRET_GH_TOKEN

set -euo pipefail

REPOS="${LUNAR_VAR_REPOS:-}"
FILENAMES="${LUNAR_VAR_FILENAMES:-catalog-info.yaml,catalog-info.yml}"
BRANCH="${LUNAR_VAR_BRANCH:-}"
SKIP_ROOT_FILE="${LUNAR_VAR_SKIP_ROOT_FILE:-true}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"

if [ -n "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
    export GH_TOKEN="$LUNAR_SECRET_GH_TOKEN"
fi
if [ -z "${GH_TOKEN:-}" ]; then
    echo "GH_TOKEN or LUNAR_SECRET_GH_TOKEN must be set — skipping" >&2
    exit 0
fi

if [ -z "$REPOS" ]; then
    echo "No repos configured (input 'repos' is empty) — nothing to scan"
    exit 0
fi

echo "Repos: $REPOS"
echo "Filenames: $FILENAMES"
[ -n "$BRANCH" ] && echo "Branch: $BRANCH"
echo "Skip root file: $SKIP_ROOT_FILE"
echo "Component id prefix: $COMPONENT_ID_PREFIX"

# helpers.sh lives next to this script; resolved at runtime via dirname.
# shellcheck disable=SC1091
source "$(dirname "$0")/helpers.sh"

BODY_FILE=$(mktemp)
ERR_FILE=$(mktemp)
trap 'rm -f "$BODY_FILE" "$ERR_FILE"' EXIT

# gh_get <url> — GET with auth, body written to $BODY_FILE, prints HTTP code.
gh_get() {
    curl -sS -o "$BODY_FILE" -w '%{http_code}' \
        -H "Authorization: Bearer $GH_TOKEN" \
        -H "Accept: $1" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$2" 2>"$ERR_FILE" || echo "000"
}

# is_catalog_file <path> — true if the path's basename is in FILENAMES.
is_catalog_file() {
    local base="${1##*/}"
    local name
    IFS=',' read -ra _names <<< "$FILENAMES"
    for name in "${_names[@]}"; do
        name="$(echo "$name" | xargs)"
        [ -z "$name" ] && continue
        [ "$base" = "$name" ] && return 0
    done
    return 1
}

CREATED=0
SCANNED=0

IFS=',' read -ra REPO_ARRAY <<< "$REPOS"
for raw_repo in "${REPO_ARRAY[@]}"; do
    SLUG="$(echo "$raw_repo" | xargs)"
    [ -z "$SLUG" ] && continue
    if [[ "$SLUG" != */* ]] || [[ "$SLUG" == */*/* ]]; then
        echo "Repo '$SLUG' is not in '<owner>/<repo>' form — skipping" >&2
        continue
    fi
    echo ""
    echo "=== Scanning $SLUG ==="

    # Resolve the ref: explicit branch, or the repo's default branch.
    REF="$BRANCH"
    if [ -z "$REF" ]; then
        CODE=$(gh_get "application/vnd.github+json" "https://api.github.com/repos/$SLUG")
        if [ "$CODE" != "200" ]; then
            echo "Could not read repo $SLUG (HTTP $CODE): $(head -c 200 "$BODY_FILE" 2>/dev/null) — skipping" >&2
            continue
        fi
        REF=$(jq -r '.default_branch // "main"' "$BODY_FILE")
    fi
    echo "Ref: $REF"

    # One recursive Git Trees call enumerates the whole repo.
    CODE=$(gh_get "application/vnd.github+json" "https://api.github.com/repos/$SLUG/git/trees/$REF?recursive=1")
    if [ "$CODE" != "200" ]; then
        echo "Git Trees API returned $CODE for $SLUG@$REF: $(head -c 200 "$BODY_FILE" 2>/dev/null) — skipping" >&2
        continue
    fi
    if [ "$(jq -r '.truncated // false' "$BODY_FILE")" = "true" ]; then
        echo "WARNING: tree for $SLUG@$REF is truncated — some catalog-info files may be missed" >&2
    fi

    # Read ALL blob paths into an array up front — the per-file fetches below
    # reuse $BODY_FILE, so the tree must be fully consumed before the loop body
    # overwrites it.
    mapfile -t ALL_PATHS < <(jq -r '.tree[]? | select(.type == "blob") | .path' "$BODY_FILE")

    # Filter to catalog-info files, create one component per file.
    for path in "${ALL_PATHS[@]}"; do
        [ -z "$path" ] && continue
        is_catalog_file "$path" || continue

        dir="$(dirname "$path")"
        if [ "$dir" = "." ]; then
            if [ "$SKIP_ROOT_FILE" = "true" ]; then
                echo "Skipping root $path in $SLUG (skip_root_file=true)"
                continue
            fi
            COMPONENT_ID="${COMPONENT_ID_PREFIX}${SLUG}"
        else
            COMPONENT_ID="${COMPONENT_ID_PREFIX}${SLUG}/${dir}"
        fi
        SCANNED=$((SCANNED + 1))

        # Fetch the file body (raw). Skip this file on any non-200.
        FILE_URL="https://api.github.com/repos/$SLUG/contents/$path?ref=$REF"
        CODE=$(gh_get "application/vnd.github.raw" "$FILE_URL")
        if [ "$CODE" != "200" ]; then
            echo "Could not fetch $path from $SLUG (HTTP $CODE) — skipping file" >&2
            continue
        fi
        YAML=$(cat "$BODY_FILE")

        if create_component "$COMPONENT_ID" "$YAML" "$SLUG/$path"; then
            CREATED=$((CREATED + 1))
        fi
    done
done

echo ""
echo "Discovery complete: scanned $SCANNED catalog-info file(s), created/updated $CREATED component(s)"
