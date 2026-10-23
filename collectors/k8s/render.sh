#!/bin/bash
# Renders each Helm chart with `helm template`, once per values set, and
# records the output in the same .k8s arrays as static manifests.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKLOAD_KINDS="Deployment|StatefulSet|DaemonSet|Job|CronJob"

FIND_CMD="${LUNAR_VAR_HELM_FIND_COMMAND:-find . -type f \( -name 'Chart.yaml' -o -name 'Chart.yml' \)}"
export HELM_VALUES="${LUNAR_VAR_HELM_VALUES-}"
export HELM_VALUES_CHAINS="${LUNAR_VAR_HELM_VALUES_CHAINS-}"
DEPENDENCY_BUILD="${LUNAR_VAR_HELM_DEPENDENCY_BUILD:-false}"
API_VERSIONS="${LUNAR_VAR_HELM_API_VERSIONS-}"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
# helm keeps its cache and repository config under HOME, which a snippet pod may not be able to write.
export HELM_CACHE_HOME="$WORK/helm/cache" HELM_CONFIG_HOME="$WORK/helm/config" HELM_DATA_HOME="$WORK/helm/data"

api_version_args=()
IFS=',' read -ra api_versions <<< "$API_VERSIONS"
for v in "${api_versions[@]}"; do
    v="${v// /}"
    [ -n "$v" ] && api_version_args+=(--api-versions "$v")
done

# A local file:// dependency is packaged into charts/ unless it's already there;
# remote ones must be vendored, or fetched with helm_dependency_build.
prepare_dependencies() {
    local dir="$1" chart_file="$2" deps_file="$2"
    if [ "$(yq '.apiVersion // ""' "$chart_file")" = "v1" ] && [ -f "$dir/requirements.yaml" ]; then
        deps_file="$dir/requirements.yaml"
    fi
    local deps
    deps=$(yq -o=json '.dependencies // []' "$deps_file" 2>/dev/null || echo '[]')
    [ "$(echo "$deps" | jq 'length')" -gt 0 ] || return 0

    if [ "$DEPENDENCY_BUILD" = "true" ]; then
        # dependency build only fetches from repositories helm knows by name.
        local url
        while IFS= read -r url; do
            timeout 300 helm repo add "$(printf '%s' "$url" | md5sum | cut -c1-12)" "$url" --force-update >/dev/null 2>&1 || true
        done < <(echo "$deps" | jq -r '.[].repository // "" | select(startswith("http"))' | sort -u)
        timeout 300 helm dependency build "$dir" >/dev/null 2>&1 || true  # a failure surfaces in the render
        return 0
    fi
    local name repo
    while IFS=$'\t' read -r name repo; do
        if compgen -G "$dir/charts/$name-*.tgz" >/dev/null || [ -f "$dir/charts/$name/Chart.yaml" ]; then
            continue
        fi
        timeout 300 helm package "$dir/${repo#file://}" -d "$dir/charts" >/dev/null 2>&1 || true
    done < <(echo "$deps" | jq -r '.[] | select((.repository // "") | startswith("file://")) | [.name, .repository] | @tsv')
}

# A valid helm release name: a lowercase DNS label of at most 53 characters.
release_name() {
    local name
    name=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-')
    while [ "${name#-}" != "$name" ]; do name="${name#-}"; done
    name="${name:0:53}"
    while [ "${name%-}" != "$name" ]; do name="${name%-}"; done
    printf '%s' "${name:-release}"
}

# Renders one values set and prints its .k8s entries as a JSON object. dir is
# the chart's path for tools; rel_dir is the path recorded in the JSON.
render() {
    local dir="$1" rel_dir="$2" release="$3" sets_json="$4" index="$5" validated_only="$6"
    local values out err valid=true
    values=$(echo "$sets_json" | jq -c --argjson i "$index" '.sets[$i]')
    out="$WORK/out/$index"
    rm -rf "$out" && mkdir -p "$out"

    local args=(template "$release" "$dir" --output-dir "$out" "${api_version_args[@]}")
    while IFS= read -r f; do
        args+=(-f "$dir/$f")
    done < <(echo "$values" | jq -r '.[] | select(. != "values.yaml")')

    local manifest
    manifest=$(jq -n --arg dir "$rel_dir" --argjson values "$values" --argjson only "$validated_only" \
        '{path: $dir, render: {chart: $dir, values: $values, validated_only: $only}}')

    if ! err=$(timeout 300 helm "${args[@]}" 2>&1 >/dev/null); then
        # Keep helm's own message: helm 4 also logs it as a level=ERROR line
        # first, and the --debug hint isn't something the user can pass here.
        local message
        message=$(printf '%s\n' "$err" | sed -n '/^Error: /,$p' | grep -v -e '^level=' -e '^Use --debug flag' | sed '/^$/d')
        [ -n "$message" ] || message="${err:-helm exited without an error message}"
        err="helm template: ${message#Error: }"
        echo "$manifest" | jq --arg error "${err:0:2000}" '{manifest: (. + {valid: false, resources: [], error: $error})}'
        return 0
    fi
    if [ "$validated_only" = "true" ]; then
        echo "$manifest" | jq '{manifest: (. + {valid: true, resources: []})}'
        return 0
    fi

    # Each template's output lands in <out>/<chart name>/<template path>; map
    # that back to the template's path in the repository.
    local docs="[]" file rel path
    docs=$(find "$out" -type f | sort | while IFS= read -r file; do
        rel="${file#"$out"/}"
        rel="${rel#*/}"
        if [ "$rel_dir" = "." ]; then path="$rel"; else path="$rel_dir/$rel"; fi
        yq -o=json '.' "$file" 2>/dev/null | jq -s --arg path "$path" 'map(select(type == "object") + {__path: $path})'
    done | jq -s 'add // []')

    local validation_error="" chart_out prefix="$rel_dir/"
    [ "$rel_dir" = "." ] && prefix=""
    if ! validation_error=$(kubeconform -strict -ignore-missing-schemas "$out" 2>&1); then
        valid=false
        for chart_out in "$out"/*; do
            validation_error="${validation_error//"$chart_out/"/"$prefix"}"
        done
    else
        validation_error=""
    fi

    echo "$docs" | jq -f "$SCRIPT_DIR/extract.jq" \
        --argjson render "{\"chart\": $(jq -n --arg d "$rel_dir" '$d'), \"values\": $values}" \
        --arg kinds "$WORKLOAD_KINDS" \
        | jq --argjson manifest "$manifest" --argjson valid "$valid" --arg error "$validation_error" \
            '{manifest: ($manifest + {valid: $valid, resources: .resources} + (if $error == "" then {} else {error: $error} end))}
             + del(.resources)'
}

chart_files=()
while IFS= read -r chart_file; do
    # Relative paths keep a ./ prefix, so a directory named like a flag never
    # reaches helm or yq as one.
    case "$chart_file" in /*|./*) ;; *) chart_file="./$chart_file" ;; esac
    chart_files+=("$chart_file")
done < <(eval "$FIND_CMD" 2>/dev/null | grep -vE '(^|/)(\.git|node_modules|vendor)(/|$)' | sort)
[ "${#chart_files[@]}" -gt 0 ] || exit 0

# Without these, every chart would be recorded as failing to render.
for tool in helm kubeconform yq jq python3; do
    command -v "$tool" >/dev/null || { echo "helm: $tool is not installed; can't render charts" >&2; exit 1; }
done

results="$WORK/results.jsonl"
: > "$results"
charts=0
for chart_file in "${chart_files[@]}"; do
    dir=$(dirname "$chart_file")
    rel_dir="${dir#./}"
    parent=$(dirname "$dir")
    # A subchart is rendered with the chart whose charts/ directory holds it.
    if [ "$(basename "$parent")" = "charts" ] && \
       { [ -f "$(dirname "$parent")/Chart.yaml" ] || [ -f "$(dirname "$parent")/Chart.yml" ]; }; then
        continue
    fi
    if [ "$(yq '.type // ""' "$chart_file" 2>/dev/null)" = "library" ]; then
        continue
    fi

    # Named for its directory, or for the chart itself at the repository root.
    release=$(basename "$dir")
    [ "$dir" = "." ] && release=$(yq '.name // "release"' "$chart_file" 2>/dev/null)
    release=$(release_name "$release")
    prepare_dependencies "$dir" "$chart_file"
    sets_json=$(python3 "$SCRIPT_DIR/values_sets.py" "$dir")
    validated_only=$(echo "$sets_json" | jq '.validated_only')
    count=$(echo "$sets_json" | jq '.sets | length')
    for ((i = 0; i < count; i++)); do
        render "$dir" "$rel_dir" "$release" "$sets_json" "$i" "$validated_only" >> "$results"
    done
    charts=$((charts + 1))
done

[ "$charts" -gt 0 ] || exit 0

jq -s '{
    manifests: [.[].manifest],
    workloads: [.[].workloads[]?],
    pdbs: [.[].pdbs[]?],
    hpas: [.[].hpas[]?],
    scaled_objects: [.[].scaled_objects[]?],
    network_policies: [.[].network_policies[]?]
}' "$results" | lunar collect -j ".k8s" -

echo "helm: $(jq -s 'length' "$results") renders of $charts charts, $(jq -s '[.[] | select(.manifest.valid == false)] | length' "$results") failed" >&2
