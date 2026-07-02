#!/bin/bash
#
# helpers.sh — shared augmentation pipeline for the backstage-catalog-info
# cataloger.
#
# Both entrypoints obtain a `catalog-info.yaml` body and hand it to
# `augment_component`, which parses it (multi-document supported), picks the
# matching Backstage `Component` entity, and writes owner / domain / tags to
# `.components["$COMPONENT_ID"]` (plus a `.domains` stub) in the Catalog JSON:
#
#   - main.sh           component-cron  → fetched via the GitHub Contents API
#   - main-on-commit.sh component-repo  → read from the repo checkout
#
# The two entrypoints differ ONLY in how they acquire the YAML. Every line of
# parsing, matching, transformation, and writing lives here, so the variants
# stay identical in behavior — change the logic once, both inherit it.
#
# Matcher / transform inputs read here (LUNAR_VAR_*):
#   component_id_annotation  (default github.com/project-slug)
#   component_id_prefix      (default github.com/)
#   domain_annotation        (default empty → use spec.domain / spec.system)
#   tag_prefix               (default bs-)
#   include_derived_tags     (default true)
#   owner_format             (default as-is) as-is | bare-name
#   default_owner            (default empty)
#
# Acquisition-only inputs (paths, branch) and secrets (GH_TOKEN) are handled
# by the entrypoints, not here.

# augment_component <component_id> <catalog_info_yaml>
#
# Silent-skips (return 0, no write) on an unparseable file or no matching
# `Component`. Returns 1 only on a hard write failure, so the run is marked
# failed (and retried) rather than silently dropping data.
augment_component() {
    local COMPONENT_ID="$1"
    local YAML="$2"

    local COMPONENT_ID_ANNOTATION="${LUNAR_VAR_COMPONENT_ID_ANNOTATION:-github.com/project-slug}"
    local COMPONENT_ID_PREFIX="${LUNAR_VAR_COMPONENT_ID_PREFIX:-github.com/}"
    local DOMAIN_ANNOTATION="${LUNAR_VAR_DOMAIN_ANNOTATION:-}"
    # `-` not `:-`: an explicit empty tag_prefix must survive so it can disable
    # prefixing (documented behavior). The hub always sets LUNAR_VAR_TAG_PREFIX —
    # to the manifest default `bs-` when unset in config, or to the user's value
    # (including "") when set — so `-bs-` only fires for a truly-unset var (direct
    # local invocation), not for a config-supplied empty string.
    local TAG_PREFIX="${LUNAR_VAR_TAG_PREFIX-bs-}"
    local INCLUDE_DERIVED_TAGS="${LUNAR_VAR_INCLUDE_DERIVED_TAGS:-true}"
    local OWNER_FORMAT="${LUNAR_VAR_OWNER_FORMAT:-as-is}"
    local DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"
    local DEFAULT_DOMAIN="${LUNAR_VAR_DEFAULT_DOMAIN:-}"

    echo "Annotation key: $COMPONENT_ID_ANNOTATION"
    echo "Component id prefix: $COMPONENT_ID_PREFIX"
    [ -n "$DOMAIN_ANNOTATION" ] && echo "Domain annotation: $DOMAIN_ANNOTATION"
    echo "Tag prefix: $TAG_PREFIX (derived: $INCLUDE_DERIVED_TAGS)"
    echo "Owner format: $OWNER_FORMAT"
    [ -n "$DEFAULT_OWNER" ] && echo "Default owner: $DEFAULT_OWNER"
    [ -n "$DEFAULT_DOMAIN" ] && echo "Default domain: $DEFAULT_DOMAIN"

    # --- Parse YAML (multi-document) ------------------------------------------
    # `yq ea '[.]' -o=json` collects all documents in a multi-doc file into a
    # single JSON array. Single-doc files yield a one-element array.
    local ENTITIES YQ_ERR
    YQ_ERR=$(mktemp)
    if ! ENTITIES=$(echo "$YAML" | yq ea '[.]' -o=json 2>"$YQ_ERR"); then
        echo "yq parse failed for $COMPONENT_ID — skipping (stderr: $(head -c 200 "$YQ_ERR"))"
        rm -f "$YQ_ERR"
        return 0
    fi
    rm -f "$YQ_ERR"

    # --- Pick the matching Component entity -----------------------------------
    # Strategy:
    #   1. Filter to kind:Component.
    #   2. If ANY entity has the configured annotation, only annotated entries
    #      participate in matching: pick the one whose
    #      `<prefix><annotation_value>` equals `$COMPONENT_ID`. If none
    #      matches, skip — refuses to guess for a repo that uses annotations.
    #   3. If NO entity has the annotation and exactly one Component exists,
    #      use it (single-Component-per-repo case).
    #   4. If NO entity has the annotation and multiple Components exist,
    #      skip — ambiguous, the YAML needs annotations to disambiguate.
    local ENTITY
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
        local COMPONENT_COUNT
        COMPONENT_COUNT=$(echo "$ENTITIES" | jq '[.[] | select((.kind // "") == "Component")] | length')
        echo "No matching Component entity for $COMPONENT_ID (Component count: $COMPONENT_COUNT) — skipping"
        return 0
    fi

    # --- Transform -------------------------------------------------------------
    # Project owner / domain / tags from the entity into the shape that goes
    # under `.components["$COMPONENT_ID"]`. Owner / domain are omitted from the
    # output when empty so we don't blow away upstream values with "".
    local ENTRY
    ENTRY=$(echo "$ENTITY" | jq \
        --arg tag_prefix "$TAG_PREFIX" \
        --arg include_derived "$INCLUDE_DERIVED_TAGS" \
        --arg owner_format "$OWNER_FORMAT" \
        --arg default_owner "$DEFAULT_OWNER" \
        --arg domain_annotation "$DOMAIN_ANNOTATION" \
        --arg default_domain "$DEFAULT_DOMAIN" \
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
            elif ($default_domain | length) > 0 then $default_domain
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
    local DOMAIN_NAME
    DOMAIN_NAME=$(echo "$ENTRY" | jq -r '.domain // ""')
    if [ -n "$DOMAIN_NAME" ]; then
        local DOMAIN_VALUE
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
            return 1
        fi
    fi

    # Single keyed object under .components — the path takes a map, not a list.
    if echo "$ENTRY" | jq --arg id "$COMPONENT_ID" '{($id): .}' | lunar catalog raw --json '.components' -; then
        echo "Wrote augmented metadata for $COMPONENT_ID"
    else
        echo "Failed to write augmented metadata for $COMPONENT_ID" >&2
        return 1
    fi
}
