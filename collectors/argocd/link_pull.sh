#!/bin/bash
# link-pull: the pull counterpart to link-push. Runs on a SERVICE repo and
# materializes that service's ArgoCD deployment posture onto its OWN Component
# JSON by reading a *predeclared* app->Application mapping from catalog-info.yaml
# and pulling the matching Application(s) from the GitOps component via
# `lunar component get-json`.
#
# Why pull instead of push: link-push writes onto the source component at its
# default-branch HEAD sha, so the posture only ever lands on post-merge main —
# a PR check evaluating at the PR's head sha can't see it. link-pull runs in the
# service's own collection, so it materializes `.cd.gitops` at the sha being
# collected (including a PR head sha) and the existing gitops/argocd policies
# gate it unchanged. It does NOT auto-correlate (that needs the image, hence a
# docker build, hence a collector-dependency feature we don't have yet) — the
# app->Application mapping is predeclared by the dev team in catalog-info.yaml.
set -e

# A cross-context reader keys everything off the repo it runs on; bail rather
# than run with a broken self-ref (mirrors link-push).
if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

CATALOG_PATHS="${LUNAR_VAR_CATALOG_INFO_PATHS:-catalog-info.yaml,catalog-info.yml}"
GITOPS_ANNOTATION="${LUNAR_VAR_GITOPS_COMPONENT_ANNOTATION:-lunar.earthly.dev/gitops-component}"
APP_ANNOTATION="${LUNAR_VAR_APPLICATION_ANNOTATION:-lunar.earthly.dev/argocd-application}"

# Direct overrides — declare the mapping in lunar-config inputs instead of the
# repo's catalog-info (handy for testing and for configs that prefer it).
GITOPS_COMPONENT="${LUNAR_VAR_GITOPS_COMPONENT:-}"
APPLICATIONS="${LUNAR_VAR_APPLICATION:-}"
MAP_SRC="input"

# Read a single annotation value from a catalog-info file; "" when absent.
read_annotation() {
    local v
    v=$(yq '.metadata.annotations["'"$2"'"]' "$1" 2>/dev/null)
    [ "$v" = "null" ] && v=""
    printf '%s' "$v"
}

# Resolve the mapping from the first catalog-info file found, unless overridden.
if [ -z "$GITOPS_COMPONENT" ]; then
    IFS=',' read -ra _paths <<< "$CATALOG_PATHS"
    for p in "${_paths[@]}"; do
        p=$(echo "$p" | tr -d '[:space:]')
        [ -n "$p" ] || continue
        [ -f "$p" ] || continue
        GITOPS_COMPONENT=$(read_annotation "$p" "$GITOPS_ANNOTATION")
        if [ -n "$GITOPS_COMPONENT" ]; then
            [ -z "$APPLICATIONS" ] && APPLICATIONS=$(read_annotation "$p" "$APP_ANNOTATION")
            MAP_SRC="catalog-info:$p"
            break
        fi
    done
fi

# No predeclared GitOps mapping -> this component isn't a pull target. Skip
# (object presence is the signal; write nothing).
if [ -z "$GITOPS_COMPONENT" ]; then
    echo "link-pull: no '$GITOPS_ANNOTATION' mapping in catalog-info and no override — skipping." >&2
    exit 0
fi
if [ "$GITOPS_COMPONENT" = "$LUNAR_COMPONENT_ID" ]; then
    echo "link-pull: gitops component == self ($LUNAR_COMPONENT_ID) — skipping." >&2
    exit 0
fi

# Pull the GitOps component's live, merged Component JSON. get-json is a direct
# hub read (authoritative + immediate; the LUNAR_HUB_* conn is already in the
# runtime). Unset the stdout-capture vars defensively — they only affect
# `lunar collect`, but keep the read hermetic.
GITOPS_JSON=$(env -u LUNAR_COLLECT_STDOUT -u LUNAR_LOG_PREFIX \
    lunar component get-json "$GITOPS_COMPONENT" 2>/tmp/pull-err) || {
    echo "link-pull: get-json '$GITOPS_COMPONENT' failed: $(head -c 300 /tmp/pull-err 2>/dev/null)" >&2
    exit 0
}

if ! echo "$GITOPS_JSON" | jq -e '.cd.gitops.applications' >/dev/null 2>&1; then
    echo "link-pull: '$GITOPS_COMPONENT' has no .cd.gitops.applications — nothing to pull." >&2
    exit 0
fi

# Declared application names (empty list = take every app the GitOps repo holds).
WANT=$(jq -nc --arg a "$APPLICATIONS" \
    '($a | split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length>0)))')

# Dedupe by name: the GitOps component's own .cd.gitops.applications can carry
# duplicate entries (its parse step appends on each hub re-run — the same
# append-not-idempotent behaviour link-push guards against), so collapse repeats
# rather than copying 14 identical "rust-service" records onto the service.
APPS=$(echo "$GITOPS_JSON" | jq -c --argjson want "$WANT" \
    '[.cd.gitops.applications[]? | select(($want | length) == 0 or (.name as $n | $want | index($n)))] | unique_by(.name)')
APP_COUNT=$(echo "$APPS" | jq 'length')
if [ "$APP_COUNT" -eq 0 ]; then
    echo "link-pull: '$GITOPS_COMPONENT' carries no Application matching [${APPLICATIONS:-<all>}] — skipping." >&2
    exit 0
fi

# Pull the AppProjects referenced by the matched apps (so non-default-project and
# the allow-list checks have their data), plus the matching raw native entries.
PROJ_NAMES=$(echo "$APPS" | jq -c '[.[].project] | unique')
PROJS=$(echo "$GITOPS_JSON" | jq -c --argjson names "$PROJ_NAMES" \
    '[.cd.gitops.projects[]? | select(.name as $n | $names | index($n))] | unique_by(.name)')
APP_PATHS=$(echo "$APPS" | jq -c '[.[].path]')
NAPPS=$(echo "$GITOPS_JSON" | jq -c --argjson paths "$APP_PATHS" \
    '[.cd.gitops.native.argocd.applications[]? | select(.path as $p | $paths | index($p))] | unique_by(.path)')
PROJ_PATHS=$(echo "$PROJS" | jq -c '[.[].path]')
NPROJS=$(echo "$GITOPS_JSON" | jq -c --argjson paths "$PROJ_PATHS" \
    '[.cd.gitops.native.argocd.projects[]? | select(.path as $p | $paths | index($p))] | unique_by(.path)')

# Materialize onto THIS (service) component — a normal in-band local collect, so
# it lands on the sha being collected. Same two-call shape as the parse step.
jq -n --argjson apps "$APPS" --argjson projs "$PROJS" \
    --argjson napps "$NAPPS" --argjson nprojs "$NPROJS" \
    '{applications: $apps, projects: $projs,
      native: {argocd: {applications: $napps, projects: $nprojs}}}' \
    | lunar collect -j ".cd.gitops" -

jq -n --arg src "$GITOPS_COMPONENT" \
    '{tool: "argocd", integration: "pull", pulled_from: $src}' \
    | lunar collect -j ".cd.gitops.source" -

# Debug breadcrumb on this component's own JSON (snippet stderr isn't queryable
# from the hub).
jq -n --arg gc "$GITOPS_COMPONENT" --arg src "$MAP_SRC" --arg req "$APPLICATIONS" \
    --argjson count "$APP_COUNT" --argjson names "$(echo "$APPS" | jq -c '[.[].name]')" \
    '{pulled_from: $gc, mapping_source: $src, requested: $req,
      pulled_count: $count, pulled: $names}' \
    | lunar collect -j ".cd.gitops._pull_debug" - 2>/dev/null || true

echo "link-pull: materialized $APP_COUNT application(s) from $GITOPS_COMPONENT onto $LUNAR_COMPONENT_ID." >&2
