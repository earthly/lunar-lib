#!/bin/bash
#
# Backstage catalog-info Monorepo Discovery Cataloger — shared by `discover` (cron)
# and `discover-on-commit` (repo hook on the repo in `repos`).
#
# Runs once per cron tick or push (global, no repo checkout). Builds a scan list from the
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
# Two passes. Pass 1 fetches every catalog-info file in the scan set (plus any
# `hierarchy_paths` match, and the `hierarchy_repos` read for Domain / System
# only) and collects its Domain / System entities — including files that won't
# become components (excluded, or not exactly one Component). The hierarchy is
# then resolved once, so a Component's `spec.system` → System `spec.domain` →
# Domain `spec.subdomainOf` chain becomes one dotted domain path wherever the
# System and Domains are declared. Pass 2 creates the components.
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
#   - No token, or both `repos` and `orgs` empty (nothing to do)
#   - Org discovery API error for an org (logged, that org skipped)
#   - A repo id that isn't `<owner>/<repo>`
#   - Git Trees / Contents API errors for a repo (logged, repo skipped)
#   - Per-file: parse error / not exactly one Component (handled in helpers.sh)
#
# Failures (exit 1, so a hub on v4.4.0+ keeps the last good catalog instead of
# saving an empty one): no repo in the scan set could be read (including org
# discovery that failed with nothing else left to scan), or a hierarchy_repos
# entry can't be read — a wrong github_host or token looks exactly like this.
#
# Inputs (LUNAR_VAR_*):
#   repos                (comma-separated <owner>/<repo>; always scanned)
#   orgs                 (comma-separated org names to auto-discover repos from)
#   hierarchy_repos      (comma-separated <owner>/<repo>; read for Domain/System only)
#   hierarchy_paths      (comma-separated path globs read for Domain/System only)
#   allowed_topics       (org-discovery allowlist; empty -> all repos pass)
#   disallowed_topics    (org-discovery blocklist; block wins over allow)
#   include_archived     (default false; include archived repos in discovery)
#   filenames            (default catalog-info.yaml,catalog-info.yml)
#   branch               (default empty -> each repo's default branch)
#   exclude_paths        (default catalog-info.yaml,catalog-info.yml)
#   github_host          (default github.com; or a GitHub Enterprise Server host)
#   component_id_prefix  (default empty -> <github_host>/)
#   ...transform + ignore-annotation inputs are read in helpers.sh
#
# Either `repos` or `orgs` (or both) must be set. Topic filters apply to the
# org-discovered set only; explicitly-listed `repos` are always scanned.
#
# Secrets:
#   GH_TOKEN — required for github.com, fetched as LUNAR_SECRET_GH_TOKEN
#   GH_ENTERPRISE_TOKEN — preferred for a GHES github_host, fetched as
#     LUNAR_SECRET_GH_ENTERPRISE_TOKEN (falls back to GH_TOKEN)

set -euo pipefail

REPOS="${LUNAR_VAR_REPOS:-}"
ORGS="${LUNAR_VAR_ORGS:-}"
HIERARCHY_REPOS="${LUNAR_VAR_HIERARCHY_REPOS:-}"
HIERARCHY_PATH_GLOBS="${LUNAR_VAR_HIERARCHY_PATHS:-}"
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
# GitHub host: github.com or a GitHub Enterprise Server hostname. A full URL is
# reduced to the bare host, as in github-org.
GITHUB_HOST=$(echo "${LUNAR_VAR_GITHUB_HOST:-github.com}" | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://##; s#/.*$##')
GITHUB_HOST="${GITHUB_HOST:-github.com}"
if [ "$GITHUB_HOST" = "github.com" ]; then
    API_BASE="https://api.github.com"
else
    API_BASE="https://$GITHUB_HOST/api/v3"
fi
# Default ids to the host so GHES subcomponents line up with github-org's
# repo-level `<host>/<owner>/<repo>` ids.
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-$GITHUB_HOST/}"

# github.com uses GH_TOKEN. A GHES host prefers GH_ENTERPRISE_TOKEN and falls
# back to GH_TOKEN, so single-token setups keep working (as github-org does).
if [ "$GITHUB_HOST" = "github.com" ]; then
    GH_AUTH_TOKEN="${LUNAR_SECRET_GH_TOKEN:-${GH_TOKEN:-}}"
    TOKEN_NAMES="GH_TOKEN or LUNAR_SECRET_GH_TOKEN"
else
    GH_AUTH_TOKEN="${LUNAR_SECRET_GH_ENTERPRISE_TOKEN:-${LUNAR_SECRET_GH_TOKEN:-${GH_ENTERPRISE_TOKEN:-${GH_TOKEN:-}}}}"
    TOKEN_NAMES="LUNAR_SECRET_GH_ENTERPRISE_TOKEN or LUNAR_SECRET_GH_TOKEN"
fi
if [ -z "$GH_AUTH_TOKEN" ]; then
    echo "$TOKEN_NAMES must be set for $GITHUB_HOST — skipping" >&2
    exit 0
fi

if [ -z "$REPOS" ] && [ -z "$ORGS" ]; then
    echo "Neither 'repos' nor 'orgs' configured — nothing to scan"
    exit 0
fi

echo "GitHub host: $GITHUB_HOST (API $API_BASE)"
[ -n "$REPOS" ] && echo "Explicit repos: $REPOS"
[ -n "$ORGS" ] && echo "Discover orgs: $ORGS"
[ -n "$HIERARCHY_REPOS" ] && echo "Hierarchy repos: $HIERARCHY_REPOS"
[ -n "$HIERARCHY_PATH_GLOBS" ] && echo "Hierarchy paths: $HIERARCHY_PATH_GLOBS"
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
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$BODY_FILE" "$ERR_FILE" "$WORK_DIR"' EXIT

# gh_get <url> — GET with auth, body written to $BODY_FILE, prints HTTP code.
gh_get() {
    curl -sS -o "$BODY_FILE" -w '%{http_code}' \
        -H "Authorization: Bearer $GH_AUTH_TOKEN" \
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
            "$API_BASE/orgs/${org}/repos?per_page=100&page=${page}&type=all")
        if [ "$code" != "200" ]; then
            echo "Org discovery for '$org' failed (HTTP $code): $(head -c 200 "$BODY_FILE" 2>/dev/null) — skipping org" >&2
            # Runs in a process substitution, so signal through the filesystem.
            touch "$WORK_DIR/org-discovery-failed"
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

# is_hierarchy_file <path> — true if the repo-relative path matches any
# HIERARCHY_PATH_GLOBS entry (same matching as exclude_paths).
is_hierarchy_file() {
    local p="$1" pat
    IFS=',' read -ra _hp <<< "$HIERARCHY_PATH_GLOBS"
    for pat in "${_hp[@]}"; do
        pat="$(echo "$pat" | xargs)"
        [ -z "$pat" ] && continue
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
    if [ -e "$WORK_DIR/org-discovery-failed" ]; then
        echo "Org discovery failed and nothing else is left to scan on $GITHUB_HOST — failing the run rather than writing an empty catalog (check github_host and the token)" >&2
        exit 1
    fi
    echo "No repositories to scan (no explicit 'repos', and org discovery matched none) — nothing to do"
    exit 0
fi
echo ""
echo "Total repositories to scan: ${#REPO_ARRAY[@]}"

ENTITIES_FILE="$WORK_DIR/hierarchy.jsonl"
PENDING_FILE="$WORK_DIR/pending.tsv"
: > "$ENTITIES_FILE"
: > "$PENDING_FILE"
SCANNED=0
FETCHED=0
SCAN_OK=0
SCAN_FAILED=0
HIER_FAILED=0

# repo_failed <create> — count a repo that couldn't be read, for the checks
# after pass 1.
repo_failed() {
    if [ "$1" = "true" ]; then
        SCAN_FAILED=$((SCAN_FAILED + 1))
    else
        HIER_FAILED=$((HIER_FAILED + 1))
    fi
}

# scan_repo <owner/repo> <create: true|false> — pass 1 for one repo. Fetches
# every catalog-info file (and hierarchy_paths match), collects its Domain /
# System entities, and queues the catalog-info files that should become
# components (create=true, not excluded) for pass 2. Repo-level API errors are
# logged and the repo skipped.
scan_repo() {
    local slug="$1" create="$2" ref code path dir id catalog hier queue body
    if [[ "$slug" != */* ]] || [[ "$slug" == */*/* ]]; then
        echo "Repo '$slug' is not in '<owner>/<repo>' form — skipping" >&2
        repo_failed "$create"
        return 0
    fi
    echo ""
    if [ "$create" = "true" ]; then
        echo "=== Scanning $slug ==="
    else
        echo "=== Scanning $slug for Domain/System entities (hierarchy_repos) ==="
    fi

    # Resolve the ref: the `branch` input for scanned repos, else the repo's
    # default branch. hierarchy_repos always read their default branch.
    ref=""
    [ "$create" = "true" ] && ref="$BRANCH"
    if [ -z "$ref" ]; then
        code=$(gh_get "application/vnd.github+json" "$API_BASE/repos/$slug")
        if [ "$code" != "200" ]; then
            echo "Could not read repo $slug (HTTP $code): $(head -c 200 "$BODY_FILE" 2>/dev/null) — skipping" >&2
            repo_failed "$create"
            return 0
        fi
        ref=$(jq -r '.default_branch // "main"' "$BODY_FILE")
    fi
    echo "Ref: $ref"

    # One recursive Git Trees call enumerates the whole repo.
    code=$(gh_get "application/vnd.github+json" "$API_BASE/repos/$slug/git/trees/$ref?recursive=1")
    if [ "$code" != "200" ]; then
        echo "Git Trees API returned $code for $slug@$ref: $(head -c 200 "$BODY_FILE" 2>/dev/null) — skipping" >&2
        repo_failed "$create"
        return 0
    fi
    [ "$create" = "true" ] && SCAN_OK=$((SCAN_OK + 1))
    if [ "$(jq -r '.truncated // false' "$BODY_FILE")" = "true" ]; then
        echo "WARNING: tree for $slug@$ref is truncated — some catalog-info files may be missed" >&2
    fi

    # Read ALL blob paths up front — the per-file fetches below reuse
    # $BODY_FILE, so the tree must be fully consumed first.
    local -a paths
    mapfile -t paths < <(jq -r '.tree[]? | select(.type == "blob") | .path' "$BODY_FILE")

    for path in "${paths[@]}"; do
        [ -z "$path" ] && continue
        catalog=false; hier=false; queue=false
        is_catalog_file "$path" && catalog=true
        is_hierarchy_file "$path" && hier=true
        [ "$catalog" = "true" ] || [ "$hier" = "true" ] || continue

        if [ "$create" = "true" ] && [ "$catalog" = "true" ]; then
            if is_excluded "$path"; then
                echo "Excluding $path in $slug from component creation (matches exclude_paths)"
            else
                queue=true
            fi
        fi

        # Fetch the file body (raw). Skip this file on any non-200.
        code=$(gh_get "application/vnd.github.raw" "$API_BASE/repos/$slug/contents/$path?ref=$ref")
        if [ "$code" != "200" ]; then
            echo "Could not fetch $path from $slug (HTTP $code) — skipping file" >&2
            continue
        fi
        FETCHED=$((FETCHED + 1))
        body="$WORK_DIR/body.$FETCHED"
        cp "$BODY_FILE" "$body"
        collect_hierarchy "$body" "$slug/$path" "$ENTITIES_FILE"

        if [ "$queue" = "true" ]; then
            dir="$(dirname "$path")"
            if [ "$dir" = "." ]; then
                id="${COMPONENT_ID_PREFIX}${slug}"
            else
                id="${COMPONENT_ID_PREFIX}${slug}/${dir}"
            fi
            printf '%s\t%s\t%s\n' "$id" "$body" "$slug/$path" >> "$PENDING_FILE"
            SCANNED=$((SCANNED + 1))
        fi
    done
    return 0
}

# --- Pass 1: fetch and collect -------------------------------------------
for raw_repo in "${REPO_ARRAY[@]}"; do
    SLUG="$(echo "$raw_repo" | xargs)"
    [ -z "$SLUG" ] && continue
    scan_repo "$SLUG" true
done

# hierarchy_repos are read for Domain / System only — never components. A repo
# already in the scan set was read above.
if [ -n "$HIERARCHY_REPOS" ]; then
    IFS=',' read -ra _hrepos <<< "$HIERARCHY_REPOS"
    for r in "${_hrepos[@]}"; do
        r="$(echo "$r" | xargs)"
        [ -z "$r" ] && continue
        [ -n "${_seen[$r]:-}" ] && continue
        _seen[$r]=1
        scan_repo "$r" false
    done
fi

# A run that reads nothing would save an empty catalog and retire every
# component this cataloger created; fail instead so the last good one stays.
if [ "$SCAN_OK" -eq 0 ] && [ "$SCAN_FAILED" -gt 0 ]; then
    echo "None of the $SCAN_FAILED repo(s) in the scan set could be read from $GITHUB_HOST — failing the run rather than writing an empty catalog (check github_host and the token)" >&2
    exit 1
fi
# Without its hierarchy repos every component would fall back to bare names.
if [ "$HIER_FAILED" -gt 0 ]; then
    echo "Could not read $HIER_FAILED hierarchy_repos repo(s) from $GITHUB_HOST — failing the run rather than resolving domains without them" >&2
    exit 1
fi

# --- Resolve the hierarchy once ------------------------------------------
if [ -s "$ENTITIES_FILE" ]; then
    jq -s '.' "$ENTITIES_FILE" > "$WORK_DIR/hierarchy.json"
    HIERARCHY_MAP=$(resolve_hierarchy "$WORK_DIR/hierarchy.json")
    HIERARCHY_ROWS=$(hierarchy_domain_rows "$WORK_DIR/hierarchy.json" "$HIERARCHY_MAP")
    echo ""
    echo "Hierarchy: $(echo "$HIERARCHY_MAP" | jq '.domains | length') Domain(s), $(echo "$HIERARCHY_MAP" | jq '.systems | length') System(s)"
    while IFS= read -r conflict; do
        [ -n "$conflict" ] && echo "WARNING: $conflict" >&2
    done < <(hierarchy_conflicts "$WORK_DIR/hierarchy.json")
    # Domains before components: hub validation drops a component whose domain
    # isn't declared. A failed write aborts so the hub retries the run.
    if echo "$HIERARCHY_ROWS" | lunar catalog raw --json '.domains' -; then
        echo "Wrote $(echo "$HIERARCHY_ROWS" | jq 'length') Domain/System row(s)"
    else
        echo "Failed to write Domain/System rows" >&2
        exit 1
    fi
fi

# --- Pass 2: create components -------------------------------------------
# Bare call — NOT wrapped in `if`. create_component returns non-zero only on a
# hard `lunar catalog raw` write failure; `set -e` then aborts the run so the
# hub retries it (the contract documented in helpers.sh) instead of exiting 0
# with a partially-written catalog. Silent skips (parse error, no/many
# Components) return 0 and continue. FD 3 keeps the loop's input away from
# anything create_component runs.
while IFS=$'\t' read -r COMPONENT_ID body src <&3; do
    create_component "$COMPONENT_ID" "$(cat "$body")" "$src"
done 3< "$PENDING_FILE"

echo ""
echo "Discovery complete: processed $SCANNED catalog-info file(s) across ${#REPO_ARRAY[@]} repo(s)"
