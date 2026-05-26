#!/bin/bash
#
# Backstage catalog-info Cataloger — augments the current Lunar component
# with owner / domain / tags read from the Backstage entity that the per-repo
# `backstage` collector parsed out of `catalog-info.yaml`.
#
# Runs once per existing component via the `component-cron` hook. Reads
# `.catalog.native.backstage` from the component's Component JSON (the
# collector's output), confirms the entity is a `Component` whose annotation
# (or ID fallback) matches `$LUNAR_COMPONENT_ID`, and writes a single
# `.components["$LUNAR_COMPONENT_ID"]` entry back into the Catalog JSON.
#
# Silent skips (exit 0 with a log line, no write) for: missing Component JSON
# data, `valid == false`, `kind != Component`, or no matching identifier.
#
# Inputs (LUNAR_VAR_*):
#   component_id_annotation   (default github.com/project-slug)
#   component_id_prefix       (default github.com/)
#   tag_prefix                (default bs-)
#   include_derived_tags      (default true)
#   owner_format              (default as-is) as-is | bare-name
#   default_owner             (default empty)
#
# No secrets, no network — the collector handles fetching + validation.

set -euo pipefail

COMPONENT_ID="${LUNAR_COMPONENT_ID:?LUNAR_COMPONENT_ID must be set by the component-cron runner}"

COMPONENT_ID_ANNOTATION="${LUNAR_VAR_COMPONENT_ID_ANNOTATION:-github.com/project-slug}"
COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"
TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX:-bs-}"
INCLUDE_DERIVED_TAGS="${LUNAR_VAR_INCLUDE_DERIVED_TAGS:-true}"
OWNER_FORMAT="${LUNAR_VAR_OWNER_FORMAT:-as-is}"
DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"

echo "Component: $COMPONENT_ID"
echo "Annotation key: $COMPONENT_ID_ANNOTATION"
echo "Component id prefix: $COMPONENT_ID_PREFIX"
echo "Tag prefix: $TAG_PREFIX (derived: $INCLUDE_DERIVED_TAGS)"
echo "Owner format: $OWNER_FORMAT"
[ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"

# --- Read collector output -------------------------------------------------
# `.catalog.native.backstage` is written by the per-repo `backstage`
# collector (collectors/backstage). If it's absent, the collector hasn't run
# on this component's repo yet, the repo has no `catalog-info.yaml`, or
# `.catalog.native` exists but doesn't include a `backstage` block.

COMPONENT_JSON=$(lunar component get-json "$COMPONENT_ID")

ENTITY=$(echo "$COMPONENT_JSON" | jq '.catalog.native.backstage // null')

if [ "$ENTITY" = "null" ]; then
    echo "No .catalog.native.backstage on $COMPONENT_ID — skipping (collector not configured, or no catalog-info.yaml)"
    exit 0
fi

# Respect the collector's lint pass. `valid: false` means the YAML parsed but
# the entity is malformed (missing kind, bad schema). Don't write augmented
# data from a known-bad source. (Note: `.valid // true` would mishandle a
# literal `false` because jq's `//` treats false as a fallback trigger.)
IS_INVALID=$(echo "$ENTITY" | jq -r '.valid == false')
if [ "$IS_INVALID" = "true" ]; then
    echo "Backstage entity for $COMPONENT_ID is marked invalid by the collector — skipping"
    exit 0
fi

KIND=$(echo "$ENTITY" | jq -r '.kind // ""')
if [ "$KIND" != "Component" ]; then
    echo "Backstage entity kind is '$KIND' (not Component) — skipping"
    exit 0
fi

# --- Identifier match ------------------------------------------------------
# Step 1: try the configured annotation. Step 2: fall back to checking that
# $LUNAR_COMPONENT_ID itself starts with $COMPONENT_ID_PREFIX (covers the
# common single-Component catalog-info.yaml with no project-slug annotation).

ANNOTATION_VALUE=$(echo "$ENTITY" | jq -r --arg key "$COMPONENT_ID_ANNOTATION" '(.metadata.annotations // {})[$key] // ""')

if [ -n "$ANNOTATION_VALUE" ]; then
    EXPECTED="${COMPONENT_ID_PREFIX}${ANNOTATION_VALUE}"
    if [ "$EXPECTED" != "$COMPONENT_ID" ]; then
        echo "Annotation '$COMPONENT_ID_ANNOTATION'='$ANNOTATION_VALUE' (→ '$EXPECTED') does not match component id '$COMPONENT_ID' — skipping"
        exit 0
    fi
    echo "Matched via annotation '$COMPONENT_ID_ANNOTATION'='$ANNOTATION_VALUE'"
else
    if [ -z "$COMPONENT_ID_PREFIX" ] || [[ "$COMPONENT_ID" != "$COMPONENT_ID_PREFIX"* ]]; then
        echo "No '$COMPONENT_ID_ANNOTATION' annotation and component id '$COMPONENT_ID' does not start with prefix '$COMPONENT_ID_PREFIX' — skipping"
        exit 0
    fi
    echo "Matched via ID prefix '$COMPONENT_ID_PREFIX' (no annotation set on entity)"
fi

# --- Transform -------------------------------------------------------------
# Project owner / domain / tags from the entity into the shape that goes
# under .components["$COMPONENT_ID"]. Owner / domain are omitted from the
# output when empty so we don't blow away upstream values with "".

ENTRY=$(echo "$ENTITY" | jq \
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

    . as $e
    | (.spec.owner // "" | tostring) as $raw_owner
    | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
    | (.spec.domain // "" | tostring) as $raw_domain
    | (.spec.system // "" | tostring) as $raw_system
    | (if ($raw_domain | length) > 0 then $raw_domain
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
# Single keyed object under .components — the path takes a map, not a list.

if echo "$ENTRY" | jq --arg id "$COMPONENT_ID" '{($id): .}' | lunar catalog raw --json '.components' -; then
    echo "Wrote augmented metadata for $COMPONENT_ID"
else
    echo "Failed to write augmented metadata for $COMPONENT_ID" >&2
    exit 1
fi
