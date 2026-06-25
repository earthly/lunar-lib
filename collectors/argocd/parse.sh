#!/bin/bash
# Shared ArgoCD parser. Sourced by main.sh (parse sub-collector) and
# link_push.sh (link-push sub-collector). `parse_argocd` echoes the normalized
# .cd.gitops body: {applications:[...], projects:[...], native:{argocd:{...}}}.

# Annotation key that carries the source component id (configurable input).
ANNOTATION_KEY="${LUNAR_VAR_COMPONENT_ANNOTATION:-lunar.earthly.dev/component}"

# argoproj CRD schemas baked into the image (see Earthfile).
ARGO_SCHEMA_LOCATION="${LUNAR_ARGO_SCHEMAS:-/opt/argo-schemas/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json}"

# Directories to ignore while scanning for YAML.
_ARGO_IGNORE_DIRS=( ".git" ".github" "node_modules" "vendor" )

# Extract container images and Argo Rollouts presence from a source path inside
# the repo (best-effort: only when manifests are plain YAML co-located here).
# $1 = source path (relative). Prints JSON {images:[...], rollout:bool}.
_scan_source_path() {
    local p="${1#./}"
    if [ -z "$p" ] || [ ! -d "$p" ]; then
        echo '{"images":[],"rollout":false}'
        return 0
    fi
    local docs images rollout
    docs=$(find "$p" -type f \( -name '*.yaml' -o -name '*.yml' \) 2>/dev/null \
        | while read -r f; do yq -o=json '.' "$f" 2>/dev/null; done | jq -s 'flatten' 2>/dev/null || echo '[]')
    images=$(echo "$docs" | jq -c '[.[] | objects |
        (.spec.template.spec.containers[]?.image),
        (.spec.template.spec.initContainers[]?.image)
        ] | map(select(. != null)) | unique' 2>/dev/null || echo '[]')
    if echo "$docs" | jq -e 'any(.[]?; .kind == "Rollout")' >/dev/null 2>&1; then
        rollout=true
    else
        rollout=false
    fi
    jq -n --argjson images "${images:-[]}" --argjson rollout "$rollout" \
        '{images: $images, rollout: $rollout}'
}

# Process a single YAML file, appending records to the aggregate temp files.
_process_argo_file() {
    local f="$1"
    local path="${f#./}"

    local docs
    docs=$(yq -o=json '.' "$f" 2>/dev/null | jq -s '.' 2>/dev/null || echo '[]')
    if ! echo "$docs" | jq -e 'any(.[]?; (.apiVersion // "") | test("^argoproj\\.io/"))' >/dev/null 2>&1; then
        return 0
    fi

    # Validate the whole file against the argoproj CRD schemas (best-effort).
    local valid
    if kubeconform -strict -ignore-missing-schemas \
        -schema-location default \
        -schema-location "$ARGO_SCHEMA_LOCATION" "$f" >/dev/null 2>&1; then
        valid=true
    else
        valid=false
    fi

    local n i doc kind
    n=$(echo "$docs" | jq 'length')
    for ((i=0; i<n; i++)); do
        doc=$(echo "$docs" | jq -c ".[$i]")
        echo "$doc" | jq -e '(.apiVersion // "") | test("^argoproj\\.io/")' >/dev/null 2>&1 || continue
        kind=$(echo "$doc" | jq -r '.kind // ""')

        case "$kind" in
        Application|ApplicationSet)
            local appspec srcpath scan
            appspec=$(echo "$doc" | jq -c 'if .kind == "ApplicationSet" then (.spec.template.spec // {}) else (.spec // {}) end')
            srcpath=$(echo "$appspec" | jq -r '(.source.path // (.sources[0].path) // "")')
            scan=$(_scan_source_path "$srcpath")

            echo "$doc" | jq -c \
                --arg path "$path" \
                --arg ann "$ANNOTATION_KEY" \
                --argjson valid "$valid" \
                --argjson appspec "$appspec" \
                --argjson scan "$scan" \
                '{
                    name: (.metadata.name // "<unnamed>"),
                    path: $path,
                    valid: $valid,
                    kind: .kind,
                    project: ($appspec.project // "default"),
                    component_annotation: (.metadata.annotations[$ann] // null),
                    sync_policy: {
                        automated: ($appspec.syncPolicy.automated != null),
                        prune: ($appspec.syncPolicy.automated.prune == true),
                        self_heal: ($appspec.syncPolicy.automated.selfHeal == true)
                    },
                    destination: {
                        server: ($appspec.destination.server // null),
                        name: ($appspec.destination.name // null),
                        namespace: ($appspec.destination.namespace // null)
                    },
                    source_ref: (($appspec.source // $appspec.sources[0]? // {}) | {
                        repoURL: (.repoURL // null),
                        path: (.path // null),
                        targetRevision: (.targetRevision // null)
                    }),
                    images: (
                        ([ $appspec.source.kustomize.images[]? ]
                         + [ $appspec.sources[]?.kustomize.images[]? ]
                         + [ $appspec.source.helm.parameters[]? | select((.name // "") | test("image"; "i")) | .value ]
                         + $scan.images)
                        | map(select(. != null and . != ""))
                        | map(sub("=.*$"; ""))
                        | unique
                    ),
                    canary: { rollout: $scan.rollout }
                } | (if .component_annotation == null then del(.component_annotation) else . end)' \
                >> "$_APPS_F"

            echo "$doc" | jq -c --arg path "$path" '{path: $path, resource: .}' >> "$_NAPPS_F"
            ;;
        AppProject)
            echo "$doc" | jq -c \
                --arg path "$path" \
                --argjson valid "$valid" \
                '{
                    name: (.metadata.name // "<unnamed>"),
                    path: $path,
                    valid: $valid,
                    is_default: ((.metadata.name // "") == "default"),
                    source_repos: (.spec.sourceRepos // []),
                    destinations: (.spec.destinations // [])
                }' >> "$_PROJS_F"

            echo "$doc" | jq -c --arg path "$path" '{path: $path, resource: .}' >> "$_NPROJS_F"
            ;;
        esac
    done
}

# Parse the cloned repo and echo the normalized .cd.gitops body.
parse_argocd() {
    _APPS_F=$(mktemp); _PROJS_F=$(mktemp); _NAPPS_F=$(mktemp); _NPROJS_F=$(mktemp)

    local find_cmd dir_pattern f
    find_cmd="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name '*.yaml' -o -name '*.yml' \)}"
    dir_pattern="(^|/)($(IFS='|'; echo "${_ARGO_IGNORE_DIRS[*]}"))(/|$)"

    while IFS= read -r f; do
        [ -n "$f" ] || continue
        _process_argo_file "$f"
    done < <(eval "$find_cmd" 2>/dev/null | grep -vE "$dir_pattern")

    jq -n \
        --argjson apps "$(jq -s '.' "$_APPS_F")" \
        --argjson projs "$(jq -s '.' "$_PROJS_F")" \
        --argjson napps "$(jq -s '.' "$_NAPPS_F")" \
        --argjson nprojs "$(jq -s '.' "$_NPROJS_F")" \
        '{applications: $apps, projects: $projs, native: {argocd: {applications: $napps, projects: $nprojs}}}'

    rm -f "$_APPS_F" "$_PROJS_F" "$_NAPPS_F" "$_NPROJS_F"
}
