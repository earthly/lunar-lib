#!/bin/bash
# link-push: correlate each ArgoCD Application to the source component it deploys
# (annotation -> image -> tag -> repoURL, first match wins), then write that
# app's deployment posture onto the source component's JSON out-of-band
# (lunar collect --component <id> --sha <sha>). Runs on the GitOps repo.
set -e

# shellcheck source=collectors/argocd/parse.sh disable=SC1091
source "$(dirname "$0")/parse.sh"

if [ -z "$LUNAR_COMPONENT_ID" ]; then
    exit 0
fi

# Ordered correlation strategies (first match wins). Default precedence
# annotation -> image -> repoURL: image-match links an app to the component that
# builds its image (the useful path when the GitOps repo is separate from the
# source), with repoURL as the weak co-located fallback.
CORRELATE_BY="${LUNAR_VAR_CORRELATE_BY:-annotation,image,repoURL}"
TAG_KEY="${LUNAR_VAR_TAG_KEY:-}"

# Hub DB connection (same pattern as snyk/semgrep/codeql collectors). Without it
# the image/tag/repoURL strategies can't resolve — degrade gracefully.
CONN_STRING=$(lunar sql connection-string 2>/dev/null) || true
if [ -z "$CONN_STRING" ] || [[ "$CONN_STRING" == *"Error"* ]]; then
    echo "link-push: hub SQL connection unavailable, skipping." >&2
    exit 0
fi
if ! command -v psql >/dev/null 2>&1; then
    apk add --no-cache postgresql-client >/dev/null 2>&1 || { echo "link-push: psql unavailable." >&2; exit 0; }
fi

sql_escape() { local s="$1"; printf '%s' "${s//\'/\'\'}"; }

# Strip a docker image reference down to registry/repo (no tag, no digest).
normalize_image() {
    local img="${1%@*}"
    local after="${img##*:}"
    if [ "$after" != "$img" ] && [ "$after" = "${after#*/}" ]; then
        img="${img%:*}"
    fi
    echo "$img"
}

# Normalize a git repoURL to a Lunar component id (github.com/org/repo).
normalize_repo_url() {
    local u="${1%.git}"
    u="${u#https://}"; u="${u#http://}"; u="${u#git@}"
    u="${u/://}"
    echo "${u%/}"
}

# Echo "component_id<TAB>git_sha" for the newest default-branch row, or nothing.
lookup_component_sha() {
    local id; id=$(sql_escape "$1")
    psql "$CONN_STRING" -t -A -F $'\t' -c \
      "SELECT component_id, git_sha FROM components_latest
       WHERE component_id = '$id' AND pr IS NULL
       LIMIT 1;" 2>/dev/null || true
}

# Echo "component_id<TAB>git_sha" for the component that builds the given image.
lookup_component_by_image() {
    local img; img=$(sql_escape "$(normalize_image "$1")")
    local self; self=$(sql_escape "$LUNAR_COMPONENT_ID")
    psql "$CONN_STRING" -t -A -F $'\t' -c \
      "SELECT component_id, git_sha FROM components_latest
       WHERE pr IS NULL AND component_id <> '$self'
         AND EXISTS (
           SELECT 1 FROM jsonb_array_elements(coalesce(component_json->'containers'->'builds','[]'::jsonb)) b
           WHERE regexp_replace(b->>'image', '(@sha256:.*)|(:[^/]+\$)', '') = '$img'
         )
       LIMIT 1;" 2>/dev/null || true
}

# Echo "component_id<TAB>git_sha" for a component whose tag_key meta maps to an
# app name (best-effort — depends on a catalog populating that field).
lookup_component_by_tag() {
    [ -n "$TAG_KEY" ] || return 0
    local key; key=$(sql_escape "$TAG_KEY")
    local val; val=$(sql_escape "$1")
    local self; self=$(sql_escape "$LUNAR_COMPONENT_ID")
    psql "$CONN_STRING" -t -A -F $'\t' -c \
      "SELECT component_id, git_sha FROM components_latest
       WHERE pr IS NULL AND component_id <> '$self'
         AND component_json #>> '{meta,$key}' = '$val'
       LIMIT 1;" 2>/dev/null || true
}

# Resolve one app (JSON on stdin var $1) to "component_id<TAB>git_sha<TAB>strategy".
resolve_app() {
    local app="$1" strat res
    IFS=',' read -ra strategies <<< "$CORRELATE_BY"
    for strat in "${strategies[@]}"; do
        strat=$(echo "$strat" | tr -d '[:space:]')
        res=""
        case "$strat" in
        annotation)
            local ann; ann=$(echo "$app" | jq -r '.component_annotation // ""')
            [ -n "$ann" ] && res=$(lookup_component_sha "$ann")
            ;;
        image)
            local imgs img
            imgs=$(echo "$app" | jq -r '.images[]? // empty')
            while IFS= read -r img; do
                [ -n "$img" ] || continue
                res=$(lookup_component_by_image "$img")
                [ -n "$res" ] && break
            done <<< "$imgs"
            ;;
        tag)
            local nm; nm=$(echo "$app" | jq -r '.name // ""')
            [ -n "$nm" ] && res=$(lookup_component_by_tag "$nm")
            ;;
        repoURL|repourl)
            local ru; ru=$(echo "$app" | jq -r '.source_ref.repoURL // ""')
            [ -n "$ru" ] && res=$(lookup_component_sha "$(normalize_repo_url "$ru")")
            ;;
        esac
        if [ -n "$res" ]; then
            printf '%s\t%s\n' "$res" "$strat"
            return 0
        fi
    done
    return 0
}

RESULT=$(parse_argocd)
APPS=$(echo "$RESULT" | jq -c '.applications')
APP_COUNT=$(echo "$APPS" | jq 'length')
if [ "$APP_COUNT" -eq 0 ]; then
    echo "link-push: no ArgoCD Applications found, nothing to link." >&2
    exit 0
fi

# Debug breadcrumb: written to THIS component's own JSON so the runtime
# resolution is observable (snippet stderr isn't queryable from the hub DB).
DBG_TOTAL=$(psql "$CONN_STRING" -t -A -c "SELECT count(*) FROM components_latest;" 2>&1 | head -c 200)
DBG_BUILDS=$(psql "$CONN_STRING" -t -A -c "SELECT count(*) FROM components_latest WHERE component_json->'containers'->'builds' IS NOT NULL;" 2>&1 | head -c 200)
DBG_FIRST_IMG=$(echo "$APPS" | jq -r '.[0].images[0]? // ""')
DBG_IMGMATCH=$(lookup_component_by_image "$DBG_FIRST_IMG" 2>&1 | tr '\t' '|' | head -c 200)
DBG_APPS=$(mktemp)

# Resolve every app, collecting {target_id, target_sha, record} lines.
RESOLVED=$(mktemp)
for ((i=0; i<APP_COUNT; i++)); do
    APP=$(echo "$APPS" | jq -c ".[$i]")
    NAME=$(echo "$APP" | jq -r '.name')
    LINE=$(resolve_app "$APP")
    jq -n --arg n "$NAME" --arg imgs "$(echo "$APP" | jq -c '.images')" --arg line "$(printf '%s' "$LINE" | tr '\t' '|')" \
        '{app:$n, images:$imgs, resolved:$line}' >> "$DBG_APPS"
    if [ -z "$LINE" ]; then
        echo "link-push: could not resolve a source component for app '$NAME' — skipping." >&2
        continue
    fi
    TARGET_ID=$(printf '%s' "$LINE" | cut -f1)
    TARGET_SHA=$(printf '%s' "$LINE" | cut -f2)
    STRAT=$(printf '%s' "$LINE" | cut -f3)
    if [ -z "$TARGET_ID" ] || [ -z "$TARGET_SHA" ]; then
        echo "link-push: app '$NAME' resolved but missing component/sha — skipping." >&2
        continue
    fi
    if [ "$TARGET_ID" = "$LUNAR_COMPONENT_ID" ]; then
        continue  # don't push onto the GitOps repo itself
    fi
    echo "link-push: app '$NAME' -> $TARGET_ID@${TARGET_SHA:0:8} (via $STRAT)" >&2
    jq -n --arg id "$TARGET_ID" --arg sha "$TARGET_SHA" --argjson rec "$APP" \
        '{target_id: $id, target_sha: $sha, record: $rec}' >> "$RESOLVED"
done

# Write the debug breadcrumb onto this component (best-effort, local collect).
jq -n --arg total "$DBG_TOTAL" --arg builds "$DBG_BUILDS" --arg self "$LUNAR_COMPONENT_ID" \
    --arg first_img "$DBG_FIRST_IMG" --arg imgmatch "$DBG_IMGMATCH" --arg cb "$CORRELATE_BY" \
    --argjson apps "$(jq -s '.' "$DBG_APPS")" \
    '{self:$self, correlate_by:$cb, components_visible:$total, components_with_builds:$builds, first_image:$first_img, image_lookup_raw:$imgmatch, apps:$apps}' \
    | lunar collect -j ".cd.gitops._link_debug" - 2>/dev/null || true
rm -f "$DBG_APPS"

# Group resolved apps by target component and push once per component.
PUSH_GROUPS=$(jq -s 'group_by(.target_id)' "$RESOLVED")
rm -f "$RESOLVED"
GROUP_COUNT=$(echo "$PUSH_GROUPS" | jq 'length')

PUSHED=0
DBG_PUSH=$(mktemp)
for ((g=0; g<GROUP_COUNT; g++)); do
    GROUP=$(echo "$PUSH_GROUPS" | jq -c ".[$g]")
    TID=$(echo "$GROUP" | jq -r '.[0].target_id')
    TSHA=$(echo "$GROUP" | jq -r '.[0].target_sha')
    RECORDS=$(echo "$GROUP" | jq -c '[.[].record]')

    # Idempotency guard. The hub periodically re-runs code collectors, and an
    # out-of-band CollectExternal write APPENDS a new collection record each time
    # (there is no supersede for external writes yet). Without this guard, the
    # target's merged .cd.gitops.applications array gains a duplicate entry on
    # every re-run. Skip when the target already carries exactly this GitOps
    # repo's app set — nothing changed, so re-pushing would only duplicate.
    # (The complete fix, which also handles an app set that genuinely changed,
    # is CollectExternal superseding prior records for the same
    # component+sha+collector — tracked as a platform follow-up.)
    WANT_NAMES=$(printf '%s' "$RECORDS" | jq -cS '[.[].name] | unique' 2>/dev/null)
    HAVE_JSON=$(psql "$CONN_STRING" -t -A -c \
        "SELECT component_json->'cd'->'gitops'->'applications'
         FROM components_latest
         WHERE component_id = '$(sql_escape "$TID")' AND pr IS NULL
           AND component_json->'cd'->'gitops'->>'linked_from' = '$(sql_escape "$LUNAR_COMPONENT_ID")'
         LIMIT 1" 2>/dev/null)
    HAVE_NAMES=$(printf '%s' "$HAVE_JSON" | jq -cS '[.[]?.name] | unique' 2>/dev/null)
    if [ -n "$HAVE_NAMES" ] && [ "$HAVE_NAMES" = "$WANT_NAMES" ]; then
        echo "link-push: $TID already linked from $LUNAR_COMPONENT_ID with the same app set — skipping (idempotent)." >&2
        jq -n --arg t "$TID" '{target:$t, ok:true, skipped:true}' >> "$DBG_PUSH"
        continue
    fi

    # The collector runtime forces stdout-capture mode (LUNAR_COLLECT_STDOUT /
    # LUNAR_LOG_PREFIX) so `lunar collect` prints instead of submitting — which
    # ignores --component. Unset both so this becomes a real CollectExternal
    # cross-component submit to the source component.
    if env -u LUNAR_COLLECT_STDOUT -u LUNAR_LOG_PREFIX lunar collect \
        --component "$TID" --sha "$TSHA" -j \
        ".cd.gitops.applications" "$RECORDS" \
        ".cd.gitops.source" '{"tool":"argocd","integration":"external"}' \
        ".cd.gitops.linked_from" "\"$LUNAR_COMPONENT_ID\"" 2>/tmp/oob-err; then
        PUSHED=$((PUSHED+1))
        jq -n --arg t "$TID" '{target:$t, ok:true}' >> "$DBG_PUSH"
    else
        echo "link-push: out-of-band push to $TID failed: $(cat /tmp/oob-err 2>/dev/null)" >&2
        jq -n --arg t "$TID" --arg e "$(head -c 300 /tmp/oob-err 2>/dev/null)" '{target:$t, ok:false, err:$e}' >> "$DBG_PUSH"
    fi
done

# Debug breadcrumb of the push results (best-effort, local collect onto self).
jq -n --argjson pushes "$(jq -s '.' "$DBG_PUSH")" --arg pushed "$PUSHED" \
    '{pushed_count:$pushed, pushes:$pushes}' \
    | lunar collect -j ".cd.gitops._push_debug" - 2>/dev/null || true
rm -f "$DBG_PUSH"

echo "link-push: pushed deployment posture to $PUSHED source component(s)." >&2
