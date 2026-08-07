#!/bin/bash
#
# Backstage catalog-info Monorepo Discovery Cataloger — SCHEDULED variant (cron).
#
# Runs once per cron tick (global, no repo checkout). Builds a scan list from the
# explicit `repos` input plus any repos auto-discovered from the `orgs` input
# (filtered by the `allowed_topics` / `disallowed_topics` GitHub-topic lists), so
# you can opt monorepos into cataloging with a repo topic instead of a
# hand-maintained list. For each repo, walks the whole file tree via the GitHub
# Git Trees API (one recursive call), finds every `catalog-info.yaml` / `.yml`
# (including files in subdirectories), fetches each via the Contents API, and
# CREATES one component per discovered file — keyed to the file's directory so a
# monorepo becomes one component per service. Owner / domain / tags come from the
# file's `Component` entity via the shared pipeline in `helpers.sh`.
#
# Component id per file (with default component_id_prefix `github.com/`):
#   catalog-info.yaml (repo root)          -> github.com/<owner>/<repo>
#   services/payments/catalog-info.yaml    -> github.com/<owner>/<repo>/services/payments
#
# By default `exclude_paths` skips a root catalog-info.yaml — the augment
# `backstage-catalog-info` cataloger owns the repo-level component — and only
# subdirectory files become (sub)components. Clear exclude_paths to also map a
# root file to the repo-level id (standalone use), or extend it to fence off
# additional paths. Dev teams can also opt a file out via the `lunar.io/ignore`
# annotation when `allow_ignore_annotation` is enabled (handled in helpers.sh).
#
# Silent skips (exit 0 with a log line, no write):
#   - No GH_TOKEN, or both `repos` and `orgs` empty (nothing to do)
#   - Org discovery API error for an org (logged, that org skipped)
#   - A repo id that isn't `<owner>/<repo>`
#   - Git Trees / Contents API errors for a repo (logged, repo skipped)
#   - Per-file: parse error / not exactly one Component (handled in helpers.sh)
#
# Inputs (LUNAR_VAR_*):
#   repos                (comma-separated <owner>/<repo>; always scanned)
#   orgs                 (comma-separated org names to auto-discover repos from)
#   allowed_topics       (org-discovery allowlist; empty -> all repos pass)
#   disallowed_topics    (org-discovery blocklist; block wins over allow)
#   include_archived     (default false; include archived repos in discovery)
#   filenames            (default catalog-info.yaml,catalog-info.yml)
#   branch               (default empty -> each repo's default branch)
#   exclude_paths        (default catalog-info.yaml,catalog-info.yml)
#   component_id_prefix  (default github.com/)
#   ...transform + ignore-annotation inputs are read in helpers.sh
#
# Either `repos` or `orgs` (or both) must be set. Topic filters apply to the
# org-discovered set only; explicitly-listed `repos` are always scanned.
#
# Secrets:
#   GH_TOKEN — required, fetched as LUNAR_SECRET_GH_TOKEN

set -euo pipefail

REPOS="${LUNAR_VAR_REPOS:-}"
ORGS="${LUNAR_VAR_ORGS:-}"
ALLOWED_TOPICS="${LUNAR_VAR_ALLOWED_TOPICS:-}"
DISALLOWED_TOPICS="${LUNAR_VAR_DISALLOWED_TOPICS:-}"
INCLUDE_ARCHIVED="${LUNAR_VAR_INCLUDE_ARCHIVED:-false}"
FILENAMES="${LUNAR_VAR_FILENAMES:-catalog-info.yaml,catalog-info.yml}"
BRANCH="${LUNAR_VAR_BRANCH:-}"
# `-` not `:-`: an explicit empty exclude_paths must survive so it can disable
# exclusion (process the root too). The hub always sets LUNAR_VAR_EXCLUDE_PATHS —
# to the manifest default when unset in config, or to the user's value (including
# "") when set — so the default only fires for a truly-unset var (local runs).
EXCLUDE_PATHS="${LUNAR_VAR_EXCLUDE_PATHS-catalog-info.yaml,catalog-info.yml}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"

if [ -n "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
    export GH_TOKEN="$LUNAR_SECRET_GH_TOKEN"
fi
if [ -z "${GH_TOKEN:-}" ]; then
    echo "GH_TOKEN or LUNAR_SECRET_GH_TOKEN must be set — skipping" >&2
    exit 0
fi

if [ -z "$REPOS" ] && [ -z "$ORGS" ]; then
    echo "Neither 'repos' nor 'orgs' configured — nothing to scan"
    exit 0
fi

[ -n "$REPOS" ] && echo "Explicit repos: $REPOS"
[ -n "$ORGS" ] && echo "Discover orgs: $ORGS"
[ -n "$ALLOWED_TOPICS" ] && echo "Allowed topics (org discovery): $ALLOWED_TOPICS"
[ -n "$DISALLOWED_TOPICS" ] && echo "Disallowed topics (org discovery): $DISALLOWED_TOPICS"
[ -n "$ORGS" ] && echo "Include archived (org discovery): $INCLUDE_ARCHIVED"
echo "Filenames: $FILENAMES"
[ -n "$BRANCH" ] && echo "Branch: $BRANCH"
echo "Exclude paths: ${EXCLUDE_PATHS:-<none>}"
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

# discover_org_repos <org> — prints, one per line, the `<owner>/<repo>` of every
# repo in <org> that passes the topic allow/blocklist (and the archived filter).
# Pages through the List-org-repositories API (100/page). Reuses $BODY_FILE, so
# call it BEFORE the scan loop (which also reuses $BODY_FILE). Emits only repo
# slugs on stdout — progress/errors go to stderr — so callers can `read` it.
discover_org_repos() {
    local org="$1" page=1 code count
    while :; do
        code=$(gh_get "application/vnd.github+json" \
            "https://api.github.com/orgs/${org}/repos?per_page=100&page=${page}&type=all")
        if [ "$code" != "200" ]; then
            echo "Org discovery for '$org' failed (HTTP $code): $(head -c 200 "$BODY_FILE" 2>/dev/null) — skipping org" >&2
            return 0
        fi
        count=$(jq 'length' "$BODY_FILE")
        if [ "$count" = "0" ]; then
            break
        fi
        # Filter by archived + topics; emit full_name. Topic set arithmetic:
        # ($allow - ($allow - $topics)) is the intersection allow ∩ topics.
        jq -r \
            --arg allowed "$ALLOWED_TOPICS" \
            --arg disallowed "$DISALLOWED_TOPICS" \
            --arg include_archived "$INCLUDE_ARCHIVED" \
            '
            def csv_set($s): ($s | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0)));
            (csv_set($allowed)) as $allow
            | (csv_set($disallowed)) as $deny
            | .[]
            | select($include_archived == "true" or (.archived != true))
            | (.topics // []) as $topics
            | select( ($allow | length) == 0 or (($allow - ($allow - $topics)) | length) > 0 )
            | select( ($deny  | length) == 0 or (($deny  - ($deny  - $topics)) | length) == 0 )
            | .full_name
            ' "$BODY_FILE"
        # A short page (< per_page) is the last one.
        if [ "$count" -lt 100 ]; then
            break
        fi
        page=$((page + 1))
    done
    return 0
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

# is_excluded <path> — true if the repo-relative path matches any EXCLUDE_PATHS
# entry, by exact path or as a glob (e.g. `legacy/*/catalog-info.yaml`).
is_excluded() {
    local p="$1" pat
    IFS=',' read -ra _ex <<< "$EXCLUDE_PATHS"
    for pat in "${_ex[@]}"; do
        pat="$(echo "$pat" | xargs)"
        [ -z "$pat" ] && continue
        # Unquoted $pat on the RHS enables glob matching; intentional.
        # shellcheck disable=SC2053
        [[ "$p" == $pat ]] && return 0
    done
    return 1
}

# Build the effective scan list: explicit `repos` plus any repos discovered from
# `orgs` (filtered by topic), de-duplicated with order preserved. Explicit repos
# are ALWAYS scanned (you named them); the topic allow/blocklist gates only the
# org-discovered set.
declare -a _collected=()

if [ -n "$REPOS" ]; then
    IFS=',' read -ra _explicit <<< "$REPOS"
    for r in "${_explicit[@]}"; do
        r="$(echo "$r" | xargs)"
        [ -n "$r" ] && _collected+=("$r")
    done
fi

if [ -n "$ORGS" ]; then
    IFS=',' read -ra _orgs <<< "$ORGS"
    for org in "${_orgs[@]}"; do
        org="$(echo "$org" | xargs)"
        [ -z "$org" ] && continue
        echo ""
        echo "=== Discovering repos in org '$org' ==="
        found_count=0
        while IFS= read -r found; do
            [ -z "$found" ] && continue
            _collected+=("$found")
            found_count=$((found_count + 1))
        done < <(discover_org_repos "$org")
        echo "Discovered $found_count repo(s) in '$org' matching the topic filter"
    done
fi

# De-duplicate, preserving first-seen order.
declare -a REPO_ARRAY=()
declare -A _seen=()
if [ ${#_collected[@]} -gt 0 ]; then
    for r in "${_collected[@]}"; do
        if [ -z "${_seen[$r]:-}" ]; then
            _seen[$r]=1
            REPO_ARRAY+=("$r")
        fi
    done
fi

if [ ${#REPO_ARRAY[@]} -eq 0 ]; then
    echo ""
    echo "No repositories to scan (no explicit 'repos', and org discovery matched none) — nothing to do"
    exit 0
fi
echo ""
echo "Total repositories to scan: ${#REPO_ARRAY[@]}"

SCANNED=0

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

        if is_excluded "$path"; then
            echo "Excluding $path in $SLUG (matches exclude_paths)"
            continue
        fi

        dir="$(dirname "$path")"
        if [ "$dir" = "." ]; then
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

        # Bare call — NOT wrapped in `if`. create_component returns non-zero
        # only on a hard `lunar catalog raw` write failure; the `set -e` at the
        # top then aborts the run so the hub retries it (the contract documented
        # in helpers.sh) instead of exiting 0 with a partially-written catalog.
        # Silent skips (parse error, no/many Components) return 0 and continue.
        create_component "$COMPONENT_ID" "$YAML" "$SLUG/$path"
    done
done

echo ""
echo "Discovery complete: processed $SCANNED catalog-info file(s) across ${#REPO_ARRAY[@]} repo(s)"
