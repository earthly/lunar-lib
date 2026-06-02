#!/bin/bash
#
# Backstage catalog-info Cataloger — augments the current Lunar component
# with owner / domain / tags read from `catalog-info.yaml` in the component's
# GitHub repo.
#
# Runs once per existing component via `component-cron`. Fetches
# `catalog-info.yaml` (or `.yml`) via the GitHub Contents API, parses the
# YAML (supports multi-document files), picks the matching `Component`
# entity, and writes a single `.components["$LUNAR_COMPONENT_ID"]` entry
# back into the Catalog JSON.
#
# Silent skips (exit 0 with a log line, no write):
#   - Component ID is not a github.com/<owner>/<repo>
#   - No catalog-info.yaml at any of the configured paths (404 from GH)
#   - YAML parse error
#   - No `Component` entity in the file
#   - Multiple Components in the file, none match `$LUNAR_COMPONENT_ID`
#   - Multiple Components in the file, none annotated, can't disambiguate
#
# Inputs (LUNAR_VAR_*):
#   paths                    (default catalog-info.yaml,catalog-info.yml)
#   branch                   (default empty → repo's default branch)
#   component_id_annotation  (default github.com/project-slug)
#   component_id_prefix      (default github.com/)
#   domain_annotation        (default empty → use spec.domain / spec.system)
#   tag_prefix               (default bs-)
#   include_derived_tags     (default true)
#   owner_format             (default as-is) as-is | bare-name
#   default_owner            (default empty)
#
# Secrets:
#   GH_TOKEN — required, fetched as LUNAR_SECRET_GH_TOKEN

set -euo pipefail

COMPONENT_ID="${LUNAR_COMPONENT_ID:?LUNAR_COMPONENT_ID must be set by the component-cron runner}"

PATHS="${LUNAR_VAR_PATHS:-catalog-info.yaml,catalog-info.yml}"
BRANCH="${LUNAR_VAR_BRANCH:-}"
COMPONENT_ID_ANNOTATION="${LUNAR_VAR_COMPONENT_ID_ANNOTATION:-github.com/project-slug}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"
DOMAIN_ANNOTATION="${LUNAR_VAR_DOMAIN_ANNOTATION:-}"
TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX:-bs-}"
INCLUDE_DERIVED_TAGS="${LUNAR_VAR_INCLUDE_DERIVED_TAGS:-true}"
OWNER_FORMAT="${LUNAR_VAR_OWNER_FORMAT:-as-is}"
DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"

if [ -n "${LUNAR_SECRET_GH_TOKEN:-}" ]; then
    export GH_TOKEN="$LUNAR_SECRET_GH_TOKEN"
elif [ -z "${GH_TOKEN:-}" ]; then
    echo "GH_TOKEN or LUNAR_SECRET_GH_TOKEN must be set" >&2
    exit 1
fi

echo "Component: $COMPONENT_ID"
echo "Paths: $PATHS"
[ -n "$BRANCH" ] && echo "Branch: $BRANCH"
echo "Annotation key: $COMPONENT_ID_ANNOTATION"
echo "Component id prefix: $COMPONENT_ID_PREFIX"
[ -n "$DOMAIN_ANNOTATION" ] && echo "Domain annotation: $DOMAIN_ANNOTATION"
echo "Tag prefix: $TAG_PREFIX (derived: $INCLUDE_DERIVED_TAGS)"
echo "Owner format: $OWNER_FORMAT"
[ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"

# --- Parse component ID into owner/repo -----------------------------------
# Only github.com/<owner>/<repo> IDs are supported. Anything else (gitlab,
# bitbucket, custom schemes) silently skips — this cataloger is GH-specific.

if [[ "$COMPONENT_ID" != "${COMPONENT_ID_PREFIX}"* ]]; then
    echo "Component id '$COMPONENT_ID' does not start with prefix '$COMPONENT_ID_PREFIX' — skipping"
    exit 0
fi
SLUG="${COMPONENT_ID#$COMPONENT_ID_PREFIX}"
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
trap 'rm -f "$ERR_FILE"' EXIT

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
echo "Fetched $FOUND_PATH from $SLUG ($(echo "$YAML" | wc -c) bytes)"

# --- Parse YAML (multi-document) ------------------------------------------
# `yq ea '[.]' -o=json` collects all documents in a multi-doc file into a
# single JSON array. Single-doc files yield a one-element array.

if ! ENTITIES=$(echo "$YAML" | yq ea '[.]' -o=json 2>"$ERR_FILE"); then
    echo "yq parse failed on $FOUND_PATH for $SLUG — skipping (stderr: $(head -c 200 "$ERR_FILE"))"
    exit 0
fi

# --- Pick the matching Component entity -----------------------------------
# Strategy:
#   1. Filter to kind:Component.
#   2. If ANY entity has the configured annotation, only annotated entries
#      participate in matching: pick the one whose
#      `<prefix><annotation_value>` equals `$LUNAR_COMPONENT_ID`. If none
#      matches, skip — refuses to guess for a repo that uses annotations.
#   3. If NO entity has the annotation and exactly one Component exists,
#      use it (single-Component-per-repo case).
#   4. If NO entity has the annotation and multiple Components exist,
#      skip — ambiguous, the YAML needs annotations to disambiguate.

ENTITY=$(echo "$ENTITIES" | jq \
    --arg ann "$COMPONENT_ID_ANNOTATION" \
    --arg prefix "$COMPONENT_ID_PREFIX" \
    --arg comp "$COMPONENT_ID" \
    '
    [.[] | select((.kind // "") == "Component")] as $components
    | ($components | map(select((.metadata.annotations // {})[$ann] // "" | tostring | length > 0))) as $annotated
    | if ($annotated | length) > 0 then
        (
          [$annotated[] | select(($prefix + ((.metadata.annotations // {})[$ann] | tostring)) == $comp)]
          | first
        ) // null
      elif ($components | length) == 1 then
        $components[0]
      else
        null
      end
    ')

if [ "$ENTITY" = "null" ] || [ -z "$ENTITY" ]; then
    COMPONENT_COUNT=$(echo "$ENTITIES" | jq '[.[] | select((.kind // "") == "Component")] | length')
    echo "No matching Component entity in $FOUND_PATH for $COMPONENT_ID (Component count: $COMPONENT_COUNT) — skipping"
    exit 0
fi

# --- Transform -------------------------------------------------------------
# Project owner / domain / tags from the entity into the shape that goes
# under `.components["$COMPONENT_ID"]`. Owner / domain are omitted from the
# output when empty so we don't blow away upstream values with "".

ENTRY=$(echo "$ENTITY" | jq \
    --arg tag_prefix "$TAG_PREFIX" \
    --arg include_derived "$INCLUDE_DERIVED_TAGS" \
    --arg owner_format "$OWNER_FORMAT" \
    --arg default_owner "$DEFAULT_OWNER" \
    --arg domain_annotation "$DOMAIN_ANNOTATION" \
    '
    def bare(s):
        if (s | type) != "string" or s == "" then s
        elif (s | contains("/")) then (s | split("/") | last)
        else s
        end;

    def format_owner(o):
        if $owner_format == "bare-name" then bare(o) else o end;

    . as $e
    | (.spec.owner // "" | tostring) as $raw_owner
    | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
    | (if ($domain_annotation | length) > 0
        then ((.metadata.annotations // {})[$domain_annotation] // "" | tostring)
        else "" end) as $annotated_domain
    | (.spec.domain // "" | tostring) as $raw_domain
    | (.spec.system // "" | tostring) as $raw_system
    | (if ($annotated_domain | length) > 0 then $annotated_domain
        elif ($raw_domain | length) > 0 then $raw_domain
        elif ($raw_system | length) > 0 then bare($raw_system)
        else "" end) as $domain
    | (.metadata.tags // []) as $base_tags
    | ($base_tags | map($tag_prefix + .)) as $prefixed
    | (if $include_derived == "true"
        then ((if ((.spec.type // "") | tostring | length) > 0
                then [$tag_prefix + "type-" + (.spec.type | tostring)] else [] end)
              + (if ((.spec.lifecycle // "") | tostring | length) > 0
                 then [$tag_prefix + "lifecycle-" + (.spec.lifecycle | tostring)] else [] end))
        else []
        end) as $derived
    | ({tags: ($prefixed + $derived)}
       + (if $owner != "" then {owner: $owner} else {} end)
       + (if $domain != "" then {domain: $domain} else {} end))
    ')

echo ""
echo "Augmenting $COMPONENT_ID with:"
echo "$ENTRY" | jq .

# --- Write to Catalog JSON -------------------------------------------------
# Hub `validateDomainRefs` rejects (and silently drops) the entire catalog
# merge save if a component references a domain that isn't present under
# `.domains`. Per-component runs accumulate via merge, so writing
# `.domains["<name>"] = {…}` here dedupes naturally across runs.
# If the same YAML carries a `kind: Domain` / `kind: System` entity with a
# matching `metadata.name`, propagate its description + owner so the domain
# row is informative rather than an empty stub.

DOMAIN_NAME=$(echo "$ENTRY" | jq -r '.domain // ""')
if [ -n "$DOMAIN_NAME" ]; then
    DOMAIN_VALUE=$(echo "$ENTITIES" | jq \
        --arg name "$DOMAIN_NAME" \
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

        ([.[]
          | select((.kind // "") == "Domain" or (.kind // "") == "System")
          | select(((.metadata.name // "") | tostring) == $name)]
         | first) as $d
        | if $d == null then {}
          else
            (($d.spec.owner // "" | tostring) as $raw_owner
             | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
             | ($d.metadata.description // "" | tostring) as $desc
             | ({}
                + (if $desc != "" then {description: $desc} else {} end)
                + (if $owner != "" then {owner: $owner} else {} end)))
          end
        ')
    echo "Writing domain '$DOMAIN_NAME':"
    echo "$DOMAIN_VALUE" | jq .
    if echo "$DOMAIN_VALUE" | jq --arg name "$DOMAIN_NAME" '{($name): .}' | lunar catalog raw --json '.domains' -; then
        echo "Wrote domain '$DOMAIN_NAME'"
    else
        echo "Failed to write domain '$DOMAIN_NAME'" >&2
        exit 1
    fi
fi

# Single keyed object under .components — the path takes a map, not a list.

if echo "$ENTRY" | jq --arg id "$COMPONENT_ID" '{($id): .}' | lunar catalog raw --json '.components' -; then
    echo "Wrote augmented metadata for $COMPONENT_ID"
else
    echo "Failed to write augmented metadata for $COMPONENT_ID" >&2
    exit 1
fi
