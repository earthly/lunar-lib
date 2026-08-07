#!/bin/bash
#
# helpers.sh — shared create pipeline for the backstage-catalog-info-monorepo
# cataloger.
#
# The entrypoint (main.sh) discovers every catalog-info.yaml in a repo and, for
# each one, calls `create_component` with a component id it built from the
# file's path (repo-level for a root file, `…/<dir>` for a file in a
# subdirectory) and the file body. `create_component` parses the file, picks
# its single `Component` entity, and writes owner / domain / tags to
# `.components["<id>"]` (plus a `.domains` stub) in the Catalog JSON.
#
# The owner/domain/tags transform and the domain-stub write are intentionally
# identical to the `backstage-catalog-info` cataloger's `helpers.sh` — this
# cataloger CREATES the component (keyed to the discovered file's path) instead
# of augmenting an existing one, but the projection of a Backstage `Component`
# into Lunar catalog fields is the same. The two plugins are distributed
# independently (each `uses:` pulls only its own directory), so the shared logic
# is duplicated here rather than sourced across plugins.
#
# Transform inputs read here (LUNAR_VAR_*):
#   domain_annotation        (default empty → use spec.domain / spec.system)
#   tag_prefix               (default bs-)
#   include_derived_tags     (default true)
#   owner_format             (default as-is) as-is | bare-name
#   default_owner            (default empty)
#   default_domain           (default empty)
#   allow_ignore_annotation  (default false)
#   ignore_annotation        (default lunar.io/ignore)
#
# Discovery inputs (repos, filenames, branch, exclude_paths,
# component_id_prefix) and the secret (GH_TOKEN) are handled by the entrypoint,
# not here.

# create_component <component_id> <catalog_info_yaml> [source_path]
#
# Silent-skips (return 0, no write) on an unparseable file, no `Component`
# entity, or more than one `Component` entity (ambiguous — this cataloger
# creates one component per file and refuses to guess which entity that is).
# Returns 1 only on a hard write failure, so the run is marked failed (and
# retried) rather than silently dropping data.
create_component() {
    local COMPONENT_ID="$1"
    local YAML="$2"
    local SRC_PATH="${3:-catalog-info.yaml}"

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
    local ALLOW_IGNORE_ANNOTATION="${LUNAR_VAR_ALLOW_IGNORE_ANNOTATION:-false}"
    local IGNORE_ANNOTATION="${LUNAR_VAR_IGNORE_ANNOTATION:-lunar.io/ignore}"

    echo ""
    echo "Creating component '$COMPONENT_ID' from $SRC_PATH"
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
        echo "yq parse failed for $SRC_PATH — skipping (stderr: $(head -c 200 "$YQ_ERR"))"
        rm -f "$YQ_ERR"
        return 0
    fi
    rm -f "$YQ_ERR"

    # --- Pick the file's Component entity -------------------------------------
    # This cataloger creates one component per discovered FILE. A file with
    # exactly one `kind: Component` maps to that entity. Zero Components → skip.
    # More than one Component in a single file is ambiguous under the
    # one-component-per-file contract, so skip and log rather than guess.
    local COMPONENT_COUNT
    COMPONENT_COUNT=$(echo "$ENTITIES" | jq '[.[] | select((.kind // "") == "Component")] | length')
    if [ "$COMPONENT_COUNT" != "1" ]; then
        echo "Expected exactly one Component in $SRC_PATH (found $COMPONENT_COUNT) — skipping"
        return 0
    fi
    local ENTITY
    ENTITY=$(echo "$ENTITIES" | jq 'first(.[] | select((.kind // "") == "Component"))')

    # --- Honor the lunar.io/ignore annotation (gated) -------------------------
    # When allow_ignore_annotation is on, a Component that carries the ignore
    # annotation set to a truthy value opts itself out — no component is created.
    # This delegates opt-out to the dev team that owns the catalog-info.yaml.
    if [ "$ALLOW_IGNORE_ANNOTATION" = "true" ]; then
        local IGNORE_VAL
        IGNORE_VAL=$(echo "$ENTITY" | jq -r \
            --arg k "$IGNORE_ANNOTATION" \
            '(.metadata.annotations // {})[$k] // "" | tostring | ascii_downcase')
        if [ "$IGNORE_VAL" = "true" ] || [ "$IGNORE_VAL" = "yes" ] || [ "$IGNORE_VAL" = "1" ]; then
            echo "$SRC_PATH carries $IGNORE_ANNOTATION=$IGNORE_VAL and allow_ignore_annotation is on — skipping"
            return 0
        fi
    fi

    # --- Transform -------------------------------------------------------------
    # Project owner / domain / tags from the entity into the shape that goes
    # under `.components["$COMPONENT_ID"]`. Owner / domain are omitted from the
    # output when empty so we don't write "" into the catalog.
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

    echo "Component entry:"
    echo "$ENTRY" | jq .

    # --- Write to Catalog JSON -------------------------------------------------
    # Hub `validateDomainRefs` rejects (and silently drops) the entire catalog
    # merge save if a component references a domain that isn't present under
    # `.domains`. Write the domain stub first. If the same file carries a
    # `kind: Domain` / `kind: System` entity with a matching `metadata.name`,
    # propagate its description + owner so the domain row is informative.
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
        echo "Created component '$COMPONENT_ID'"
    else
        echo "Failed to create component '$COMPONENT_ID'" >&2
        return 1
    fi
}
