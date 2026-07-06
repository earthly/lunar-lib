#!/bin/bash
#
# Backstage Cataloger — sync entities from a Backstage instance into Lunar.
#
# Fetches <api_path_prefix>/catalog/entities (paginated), routes:
#   - Component, API, Resource → .components (keyed by <id_prefix><annotation value>)
#   - Domain, System          → .domains    (keyed by metadata.name)
# Applies owner_format (as-is | bare-name), derived bs-type-*/bs-lifecycle-*
# tags, default_owner fallback, and an optional Backstage filter expression.
#
# Inputs (LUNAR_VAR_*):
#   backstage_url             (required) Base URL of the Backstage instance
#   api_path_prefix           (default /api) Path prefix before /catalog/entities;
#                             set to "" for a Backstage API mounted at the root
#   entity_kinds              (default Component,Domain) Comma-separated kinds
#   namespace                 (default default) Namespace, or "*" for all
#   component_id_annotation   (default github.com/project-slug)
#   component_id_prefix       (default github.com/)
#   tag_prefix                (default bs-)
#   include_derived_tags      (default true)
#   owner_format              (default as-is) as-is | bare-name
#   default_owner             (default empty)
#   domain_default_description (default empty)
#   filter                    (default empty) Raw Backstage filter clause
#
# Secret: LUNAR_SECRET_BACKSTAGE_TOKEN (optional; sent as Bearer if present)

set -euo pipefail

BACKSTAGE_URL="${LUNAR_VAR_BACKSTAGE_URL:?backstage_url input is required}"
BACKSTAGE_URL="${BACKSTAGE_URL%/}"

# Path prefix prepended before `/catalog/entities`. Defaults to `/api` (the
# standard Backstage layout). Set to "" for an instance whose catalog API is
# mounted at the root — e.g. behind an API gateway that strips the `/api` hop.
# `-` not `:-` (same treatment as TAG_PREFIX below): an explicit empty value
# must survive so it can disable the prefix. The hub always sets
# LUNAR_VAR_API_PATH_PREFIX — to the manifest default `/api` when unset in
# config, or the user's value (including "") when set — so `-/api` only fires
# for a truly-unset var (direct local invocation), not a config-supplied "".
API_PATH_PREFIX="${LUNAR_VAR_API_PATH_PREFIX-/api}"
# Normalize: drop any trailing slash, and ensure a non-empty value leads with a
# slash — so `api`, `/api`, and `/api/` all resolve to `/api`, and "" stays "".
API_PATH_PREFIX="${API_PATH_PREFIX%/}"
if [ -n "$API_PATH_PREFIX" ] && [ "${API_PATH_PREFIX#/}" = "$API_PATH_PREFIX" ]; then
    API_PATH_PREFIX="/$API_PATH_PREFIX"
fi

ENTITY_KINDS="${LUNAR_VAR_ENTITY_KINDS:-Component,Domain}"
NAMESPACE="${LUNAR_VAR_NAMESPACE:-default}"
COMPONENT_ID_ANNOTATION="${LUNAR_VAR_COMPONENT_ID_ANNOTATION:-github.com/project-slug}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"
# `-` not `:-`: an explicit empty tag_prefix must survive so it can disable
# prefixing (documented behavior). The hub always sets LUNAR_VAR_TAG_PREFIX —
# to the manifest default `bs-` when unset in config, or to the user's value
# (including "") when set — so `-bs-` only fires for a truly-unset var (direct
# local invocation), not for a config-supplied empty string.
TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX-bs-}"
INCLUDE_DERIVED_TAGS="${LUNAR_VAR_INCLUDE_DERIVED_TAGS:-true}"
OWNER_FORMAT="${LUNAR_VAR_OWNER_FORMAT:-as-is}"
DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"
DOMAIN_DEFAULT_DESCRIPTION="${LUNAR_VAR_DOMAIN_DEFAULT_DESCRIPTION:-}"
USER_FILTER="${LUNAR_VAR_FILTER:-}"

PAGE_SIZE="${PAGE_SIZE:-200}"
MAX_RETRIES="${MAX_RETRIES:-5}"
INITIAL_BACKOFF="${INITIAL_BACKOFF:-5}"
BATCH_SIZE="${BATCH_SIZE:-1000}"

AUTH_HEADER=()
if [ -n "${LUNAR_SECRET_BACKSTAGE_TOKEN:-}" ]; then
    AUTH_HEADER=(-H "Authorization: Bearer $LUNAR_SECRET_BACKSTAGE_TOKEN")
fi

echo "Cataloging Backstage entities from: $BACKSTAGE_URL${API_PATH_PREFIX}/catalog/entities"
echo "Kinds: $ENTITY_KINDS"
echo "Namespace: $NAMESPACE"
echo "Component id: $COMPONENT_ID_PREFIX + <annotation '$COMPONENT_ID_ANNOTATION'>"
echo "Tag prefix: $TAG_PREFIX (derived: $INCLUDE_DERIVED_TAGS)"
echo "Owner format: $OWNER_FORMAT"
[ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"
[ -n "$USER_FILTER" ] && echo "Extra filter: $USER_FILTER"

# --- Build filter query --------------------------------------------------
# Backstage semantics: multiple ?filter= params are OR'd; commas within a
# single filter are AND'd. We want (kind=X OR kind=Y) AND namespace AND user
# filter — i.e. include namespace + user filter in every kind clause.
FILTER_QUERY=""
IFS=',' read -ra KIND_ARRAY <<< "$ENTITY_KINDS"
for kind in "${KIND_ARRAY[@]}"; do
    kind=$(echo "$kind" | xargs)
    [ -z "$kind" ] && continue

    CLAUSE="kind=$kind"
    if [ "$NAMESPACE" != "*" ] && [ -n "$NAMESPACE" ]; then
        CLAUSE="$CLAUSE,metadata.namespace=$NAMESPACE"
    fi
    if [ -n "$USER_FILTER" ]; then
        CLAUSE="$CLAUSE,$USER_FILTER"
    fi
    FILTER_QUERY="${FILTER_QUERY}&filter=$CLAUSE"
done

# --- Paginated fetch -----------------------------------------------------
fetch_page() {
    local offset="$1"
    local url="$BACKSTAGE_URL${API_PATH_PREFIX}/catalog/entities/by-query?limit=$PAGE_SIZE${offset:+&after=$offset}$FILTER_QUERY"

    local attempt=1
    local backoff=$INITIAL_BACKOFF
    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        local response_file
        response_file=$(mktemp)
        local http_status
        http_status=$(curl -sS -o "$response_file" -w '%{http_code}' \
            "${AUTH_HEADER[@]}" \
            -H "Accept: application/json" \
            "$url" 2>/dev/null || echo "000")
        local body
        body=$(cat "$response_file")
        rm -f "$response_file"

        if [ "$http_status" = "200" ]; then
            echo "$body"
            return 0
        fi

        if [ "$http_status" = "429" ] || [[ "$http_status" =~ ^5 ]] || [ "$http_status" = "000" ]; then
            echo "Transient $http_status from Backstage (attempt $attempt/$MAX_RETRIES, offset=$offset), waiting ${backoff}s..." >&2
            sleep "$backoff"
            backoff=$((backoff * 2))
            attempt=$((attempt + 1))
            continue
        fi

        echo "Error from Backstage ($http_status) at offset=$offset:" >&2
        echo "$body" | head -c 500 >&2
        echo "" >&2
        return 1
    done
    echo "Failed to fetch page at offset=$offset after $MAX_RETRIES attempts" >&2
    return 1
}

ALL_ENTITIES=$(mktemp)
trap 'rm -f "$ALL_ENTITIES" "${ALL_ENTITIES}.chunk" "${ALL_ENTITIES}.new" "${ALL_ENTITIES}.entries"' EXIT
echo "[]" > "$ALL_ENTITIES"

OFFSET=0
TOTAL_FETCHED=0
while true; do
    PAGE=$(fetch_page "$OFFSET")
    PAGE_COUNT=$(echo "$PAGE" | jq 'length')

    if [ "$PAGE_COUNT" -eq 0 ]; then
        break
    fi

    echo "$PAGE" > "${ALL_ENTITIES}.chunk"
    jq -s 'add' "$ALL_ENTITIES" "${ALL_ENTITIES}.chunk" > "${ALL_ENTITIES}.new"
    mv "${ALL_ENTITIES}.new" "$ALL_ENTITIES"
    rm -f "${ALL_ENTITIES}.chunk"

    TOTAL_FETCHED=$((TOTAL_FETCHED + PAGE_COUNT))
    echo "  fetched offset=$OFFSET page=$PAGE_COUNT total=$TOTAL_FETCHED"

    if [ "$PAGE_COUNT" -lt "$PAGE_SIZE" ]; then
        break
    fi

    OFFSET=$((OFFSET + PAGE_SIZE))
done

echo "Total entities fetched: $TOTAL_FETCHED"

if [ "$TOTAL_FETCHED" -eq 0 ]; then
    echo "No Backstage entities matched the filter; nothing to write"
    exit 0
fi

# --- Transform to Lunar catalog entries ----------------------------------
# Components from Component / API / Resource keyed by <prefix><annotation>.
# Domains from Domain / System keyed by metadata.name.
# spec.domain (verbatim) takes precedence; fall back to spec.system stripped
# to bare name so it lines up with how we keyed Systems above.

COMPONENTS=$(jq \
    --arg annotation "$COMPONENT_ID_ANNOTATION" \
    --arg id_prefix "$COMPONENT_ID_PREFIX" \
    --arg tag_prefix "$TAG_PREFIX" \
    --arg include_derived "$INCLUDE_DERIVED_TAGS" \
    --arg owner_format "$OWNER_FORMAT" \
    --arg default_owner "$DEFAULT_OWNER" \
    '
    def bare(s):
        if (s | type) != "string" or s == "" then s
        elif (s | contains("/")) then (s | split("/") | last)
        else s
        end;

    def format_owner(o):
        if $owner_format == "bare-name" then bare(o) else o end;

    def domain_ref(e):
        (e.spec.domain // "") as $d
        | (e.spec.system // "") as $s
        | if ($d | tostring | length) > 0 then ($d | tostring)
          elif ($s | tostring | length) > 0 then bare($s | tostring)
          else ""
          end;

    [.[]
     | select(.kind == "Component" or .kind == "API" or .kind == "Resource")
     | . as $e
     | (.metadata.annotations // {}) as $ann
     | ($ann[$annotation] // "") as $ann_val
     | select(($ann_val | tostring | length) > 0)
     | ($id_prefix + ($ann_val | tostring)) as $id
     | (.spec.owner // "" | tostring) as $raw_owner
     | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
     | (.metadata.tags // []) as $base_tags
     | ($base_tags | map($tag_prefix + .)) as $prefixed
     | (if $include_derived == "true"
        then ((if ((.spec.type // "") | tostring | length) > 0
                then [$tag_prefix + "type-" + (.spec.type | tostring)] else [] end)
              + (if ((.spec.lifecycle // "") | tostring | length) > 0
                 then [$tag_prefix + "lifecycle-" + (.spec.lifecycle | tostring)] else [] end))
        else []
        end) as $derived
     | domain_ref($e) as $domain
     | {key: $id, value:
         ({tags: ($prefixed + $derived)}
          + (if $owner != "" then {owner: $owner} else {} end)
          + (if $domain != "" then {domain: $domain} else {} end))}
    ]
    | from_entries' "$ALL_ENTITIES")

DOMAINS=$(jq \
    --arg owner_format "$OWNER_FORMAT" \
    --arg default_owner "$DEFAULT_OWNER" \
    --arg default_desc "$DOMAIN_DEFAULT_DESCRIPTION" \
    '
    def bare(s):
        if (s | type) != "string" or s == "" then s
        elif (s | contains("/")) then (s | split("/") | last)
        else s
        end;

    def format_owner(o):
        if $owner_format == "bare-name" then bare(o) else o end;

    [.[]
     | select(.kind == "Domain" or .kind == "System")
     | .metadata.name as $name
     | (.spec.owner // "" | tostring) as $raw_owner
     | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
     | (.metadata.description // "" | tostring) as $raw_desc
     | (if $raw_desc == "" then $default_desc else $raw_desc end) as $desc
     | {key: $name, value:
         ({}
          + (if $desc != "" then {description: $desc} else {} end)
          + (if $owner != "" then {owner: $owner} else {} end))}
    ]
    | from_entries' "$ALL_ENTITIES")

COMPONENT_COUNT=$(echo "$COMPONENTS" | jq 'length')
DOMAIN_COUNT=$(echo "$DOMAINS" | jq 'length')

echo "Components to write: $COMPONENT_COUNT"
echo "Domains to write:    $DOMAIN_COUNT"

# --- Write to Lunar catalog ----------------------------------------------
# Hub validateDomainRefs requires every component.domain to exist under
# catalog .domains, so write domains first.

if [ "$DOMAIN_COUNT" -gt 0 ]; then
    if echo "$DOMAINS" | lunar catalog raw --json '.domains' -; then
        echo "Wrote $DOMAIN_COUNT domains"
    else
        echo "Failed to write domains" >&2
        exit 1
    fi
fi

if [ "$COMPONENT_COUNT" -eq 0 ]; then
    echo ""
    echo "Backstage sync complete: 0 components, $DOMAIN_COUNT domains"
    exit 0
fi

WRITTEN=0
FAILED=0
if [ "$COMPONENT_COUNT" -le "$BATCH_SIZE" ]; then
    if echo "$COMPONENTS" | lunar catalog raw --json '.components' -; then
        WRITTEN=$COMPONENT_COUNT
    else
        FAILED=$COMPONENT_COUNT
    fi
else
    echo "$COMPONENTS" | jq 'to_entries' > "${ALL_ENTITIES}.entries"
    BATCH_NUM=0
    while true; do
        START=$((BATCH_NUM * BATCH_SIZE))
        if [ "$START" -ge "$COMPONENT_COUNT" ]; then break; fi
        END=$((START + BATCH_SIZE))
        if [ "$END" -gt "$COMPONENT_COUNT" ]; then END=$COMPONENT_COUNT; fi
        BATCH_NUM=$((BATCH_NUM + 1))
        COUNT=$((END - START))
        BATCH=$(jq --argjson s "$START" --argjson c "$COUNT" \
            '.[$s:$s+$c] | from_entries' "${ALL_ENTITIES}.entries")
        if echo "$BATCH" | lunar catalog raw --json '.components' -; then
            WRITTEN=$((WRITTEN + COUNT))
            echo "  batch $BATCH_NUM: wrote $COUNT components ($WRITTEN/$COMPONENT_COUNT)"
        else
            FAILED=$((FAILED + COUNT))
            echo "  batch $BATCH_NUM: FAILED ($COUNT components, continuing)" >&2
        fi
    done
fi

echo ""
echo "Backstage sync complete: $WRITTEN components written, $DOMAIN_COUNT domains written"
if [ "$FAILED" -gt 0 ]; then
    echo "  $FAILED components failed to write" >&2
    exit 1
fi
