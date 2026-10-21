#!/bin/bash
#
# helpers.sh — shared pipeline for the backstage-catalog-info-monorepo
# cataloger.
#
# main.sh runs two passes over the scan set. Pass 1 hands every fetched file to
# `collect_hierarchy`, which keeps its `Domain` / `System` entities. main.sh
# then resolves the hierarchy once (`resolve_hierarchy`), writes a `.domains`
# row per declared Domain / System (`hierarchy_domain_rows`), and in pass 2
# calls `create_component` for each catalog-info file, which picks the file's
# single `Component` and writes owner / domain / tags to `.components["<id>"]`.
#
# The owner / tag transform and the dotted-path resolver match the
# `backstage-catalog-info` cataloger's helpers.sh and catalogers/backstage —
# change them together. The difference is scope: this cataloger resolves a
# Component's System / Domain chain across every file it scans, not just the
# file the Component is in. The plugins are distributed independently (each
# `uses:` pulls only its own directory), so the logic is duplicated rather than
# sourced across plugins.
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
# Discovery inputs (repos, orgs, hierarchy_repos, hierarchy_paths, filenames,
# branch, exclude_paths, component_id_prefix) and the secret (GH_TOKEN) are
# handled by the entrypoint, not here.

# Resolved hierarchy, set by main.sh after pass 1. Empty maps (a scan with no
# Domain / System entities) make every lookup fall back to the bare name.
HIERARCHY_MAP='{"domains":{},"systems":{}}'
HIERARCHY_ROWS='{}'

# collect_hierarchy <yaml_file> <source_path> <out_jsonl>
#
# Appends each `Domain` / `System` entity in the file to <out_jsonl>, one JSON
# object per line, tagged with its source path for conflict warnings. Reads
# every file it's given — including files skipped for component creation — so
# a hierarchy declared anywhere in the scan set resolves. Unparseable files are
# logged and skipped.
collect_hierarchy() {
    local file="$1" src="$2" out="$3" entities
    if ! entities=$(yq ea '[.]' -o=json "$file" 2>/dev/null); then
        echo "yq parse failed for $src — not reading its Domain/System entities"
        return 0
    fi
    # Malformed entities (non-object metadata / spec) are dropped here so they
    # can't break the resolver for the whole run.
    if ! echo "$entities" | jq -c --arg src "$src" '
        .[]
        | select(type == "object")
        | select((.kind // "") == "Domain" or (.kind // "") == "System")
        | select(((.metadata // {}) | type) == "object" and ((.spec // {}) | type) == "object")
        | select(((.metadata.name // "") | tostring | length) > 0)
        | . + {__src: $src}' >> "$out"; then
        echo "Could not read Domain/System entities from $src — skipping"
    fi
}

# resolve_hierarchy <entities_json_array_file>
#
# Prints {domains: {name: dotted-path}, systems: {name: dotted-path}}. Lunar
# encodes hierarchy as dotted names (`a.b.c` is a child of `a.b`): a Domain's
# key is its full `spec.subdomainOf` ancestry, and a System nests under the
# domain it belongs to (`spec.domain`). A reference to a parent that wasn't
# collected contributes its bare name as one segment and stops the walk there.
# Cycles are broken defensively so a malformed catalog can't hang the run.
resolve_hierarchy() {
    jq '
        def bare(s):
            if (s | type) != "string" or s == "" then s
            elif (s | contains("/")) then (s | split("/") | last)
            else s
            end;

        ( [ .[] | select(.kind == "Domain")
            | { key: (.metadata.name | tostring),
                value: ((.spec.subdomainOf // "") | tostring | if . == "" then null else bare(.) end) } ]
          | from_entries ) as $domain_parent
        | ( [ .[] | select(.kind == "System")
              | { key: (.metadata.name | tostring),
                  value: ((.spec.domain // "") | tostring | if . == "" then null else bare(.) end) } ]
            | from_entries ) as $system_parent
        | ( def dpath($n; $seen):
              if $n == null or $n == "" then []
              elif ($seen | index($n)) then []
              else ($domain_parent[$n] // null) as $p
                   | (if $p == null then [$n] else dpath($p; $seen + [$n]) + [$n] end)
              end;
            {
              domains: ( [ $domain_parent | keys[] as $k
                           | { key: $k, value: (dpath($k; []) | join(".")) } ] | from_entries ),
              systems: ( [ $system_parent | to_entries[] | .key as $k | (.value) as $dom
                           | { key: $k,
                               value: (if $dom == null then $k
                                       else (dpath($dom; []) | join(".")) as $dp
                                            | (if $dp == "" then $k else $dp + "." + $k end)
                                       end) } ] | from_entries )
            } )
        ' "$1"
}

# hierarchy_domain_rows <entities_json_array_file> <hierarchy_map_json>
#
# Prints one `.domains` row per declared Domain / System, keyed by its dotted
# path and carrying its description / owner.
hierarchy_domain_rows() {
    local OWNER_FORMAT="${LUNAR_VAR_OWNER_FORMAT:-as-is}"
    local DEFAULT_OWNER="${LUNAR_VAR_DEFAULT_OWNER:-}"
    jq \
        --argjson paths "$2" \
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

        [ .[]
          | (.metadata.name | tostring) as $name
          | (if .kind == "System" then ($paths.systems[$name] // $name)
             else ($paths.domains[$name] // $name) end) as $key
          | (.spec.owner // "" | tostring) as $raw_owner
          | (if $raw_owner == "" then $default_owner else format_owner($raw_owner) end) as $owner
          | (.metadata.description // "" | tostring) as $desc
          | { key: $key, value:
              ({}
               + (if $desc != "" then {description: $desc} else {} end)
               + (if $owner != "" then {owner: $owner} else {} end)) } ]
        | from_entries
        ' "$1"
}

# hierarchy_conflicts <entities_json_array_file>
#
# Prints one line per Domain / System name declared with different parents in
# different files. The resolver keeps the last one read.
hierarchy_conflicts() {
    jq -r '
        def bare(s):
            if (s | type) != "string" or s == "" then s
            elif (s | contains("/")) then (s | split("/") | last)
            else s
            end;
        def parent:
            (if .kind == "System" then .spec.domain else .spec.subdomainOf end) // ""
            | tostring | bare(.);

        group_by([.kind, (.metadata.name | tostring)])[]
        | select((map(parent) | unique | length) > 1)
        | "\(.[0].kind) \(.[0].metadata.name) has different parents: "
          + (map("\(parent | if . == "" then "<none>" else . end) (\(.__src))") | join(", "))
          + " — using the last"
        ' "$1"
}

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
    # Non-object documents (a bare string, a list) are not entities; filter them
    # first so one odd file can't crash the jq and abort the whole run.
    COMPONENT_COUNT=$(echo "$ENTITIES" | jq '[.[] | select(type == "object") | select((.kind // "") == "Component")] | length')
    if [ "$COMPONENT_COUNT" != "1" ]; then
        echo "Expected exactly one Component in $SRC_PATH (found $COMPONENT_COUNT) — skipping"
        return 0
    fi
    local ENTITY
    ENTITY=$(echo "$ENTITIES" | jq 'first(.[] | select(type == "object") | select((.kind // "") == "Component"))')

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
        --argjson paths "$HIERARCHY_MAP" \
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
        # Explicit overrides (domain annotation, default_domain) are used as-is;
        # spec.domain / spec.system resolve to their dotted path when the
        # hierarchy declares them, else fall back to the bare name.
        | (if ($annotated_domain | length) > 0 then $annotated_domain
            elif ($raw_domain | length) > 0 then ($paths.domains[bare($raw_domain)] // $raw_domain)
            elif ($raw_system | length) > 0 then (bare($raw_system) as $sn | $paths.systems[$sn] // $sn)
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
    # Hub domain validation drops a component whose domain isn't declared under
    # `.domains`. main.sh already wrote a row for every declared Domain /
    # System; add an empty stub only for a domain that isn't one of them (an
    # annotation, a literal spec.domain, default_domain, or an unresolved ref).
    local DOMAIN_NAME
    DOMAIN_NAME=$(echo "$ENTRY" | jq -r '.domain // ""')
    if [ -n "$DOMAIN_NAME" ] && ! echo "$HIERARCHY_ROWS" | jq -e --arg d "$DOMAIN_NAME" 'has($d)' >/dev/null; then
        echo "Writing domain stub '$DOMAIN_NAME'"
        if jq -n --arg name "$DOMAIN_NAME" '{($name): {}}' | lunar catalog raw --json '.domains' -; then
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
