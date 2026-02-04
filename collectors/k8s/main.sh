#!/bin/bash
# Collects Kubernetes manifests and workload, PDB, and HPA metadata. Enforces K8s best practices.
set -e

# Source helper function for helm template detection
source "$(dirname "$0")/helm.sh"

# Directories to ignore
IGNORE_DIRS=(
    ".github"
    ".git"
    "node_modules"
    "vendor"
    "templates"
    "charts"
    "helm"
    "openapi"
)

# File names to ignore
IGNORE_FILES=(
    "catalog-info.yaml"
    "catalog-info.yml"
    "Chart.yaml"
    "Chart.yml"
)

# Workload kinds we track
WORKLOAD_KINDS="Deployment|StatefulSet|DaemonSet|Job|CronJob"

# Function to process a single file
process_file() {
    local f="$1"
    
    # Normalize path (remove leading ./)
    local path="${f#./}"
    
    # Read file content once
    content="$(cat "$f")"
    
    # Skip files that don't look like K8s manifests: require top-level .apiVersion and .kind
    if ! yq -e -s 'map(select(.apiVersion and .kind)) | length > 0' "$f" >/dev/null 2>&1; then
        return 0
    fi
    
    # Skip Helm templates
    if is_helm_template "$content"; then
        return 0
    fi
    
    # Validate the k8s manifest using kubeconform
    validation_output=""
    if validation_output=$(kubeconform -strict -ignore-missing-schemas "$f" 2>&1); then
        valid=true
        validation_error=""
    else
        valid=false
        validation_error="$validation_output"
    fi
    
    # Parse YAML to JSON (handle multi-document YAML)
    docs=$(echo "$content" | yq -o=json -s '.' 2>/dev/null || echo '[]')
    
    # Extract resources from the file
    resources=$(echo "$docs" | jq '[.[] | select(.kind != null) | {kind: .kind, name: .metadata.name, namespace: (.metadata.namespace // "default")}]')
    
    # Build manifest entry
    manifest=$(jq -n \
        --arg path "$path" \
        --argjson valid "$valid" \
        --arg error "$validation_error" \
        --argjson resources "$resources" \
        '{
            path: $path,
            valid: $valid,
            resources: $resources
        } + (if $error == "" then {} else {error: $error} end)')
    
    # Extract workloads
    workloads=$(echo "$docs" | jq --arg path "$path" --arg kinds "$WORKLOAD_KINDS" '[
        .[] | 
        select(.kind | test($kinds)) |
        {
            kind: .kind,
            name: .metadata.name,
            namespace: (.metadata.namespace // "default"),
            path: $path,
            replicas: (.spec.replicas // 1),
            pod_spec: (
                if .kind == "CronJob" then .spec.jobTemplate.spec.template.spec
                elif .kind == "Job" then .spec.template.spec
                else .spec.template.spec
                end
            )
        }
    ]')
    
    # Process containers in workloads
    workloads_with_containers=$(echo "$workloads" | jq '[
        .[] |
        . as $w |
        {
            kind: .kind,
            name: .name,
            namespace: .namespace,
            path: .path,
            replicas: .replicas,
            containers: [
                (.pod_spec.containers // [])[] |
                {
                    name: .name,
                    image: (.image // null),
                    has_resources: ((.resources.requests != null) or (.resources.limits != null)),
                    has_requests: (.resources.requests != null),
                    has_limits: (.resources.limits != null),
                    cpu_request: (.resources.requests.cpu // null),
                    cpu_limit: (.resources.limits.cpu // null),
                    memory_request: (.resources.requests.memory // null),
                    memory_limit: (.resources.limits.memory // null),
                    has_liveness_probe: (.livenessProbe != null),
                    has_readiness_probe: (.readinessProbe != null),
                    runs_as_non_root: (if .securityContext.runAsNonRoot == null then (($w.pod_spec.securityContext.runAsNonRoot == true) // false) else (.securityContext.runAsNonRoot == true) end),
                    read_only_root_fs: ((.securityContext.readOnlyRootFilesystem == true) // false),
                    privileged: ((.securityContext.privileged == true) // false)
                }
            ]
        }
    ]')
    
    # Extract PDBs
    pdbs=$(echo "$docs" | jq --arg path "$path" '[
        .[] |
        select(.kind == "PodDisruptionBudget") |
        {
            name: .metadata.name,
            namespace: (.metadata.namespace // "default"),
            path: $path,
            target_workload: (.spec.selector.matchLabels.app // .spec.selector.matchLabels["app.kubernetes.io/name"] // null),
            min_available: (.spec.minAvailable // null),
            max_unavailable: (.spec.maxUnavailable // null)
        }
    ]')
    
    # Extract HPAs
    hpas=$(echo "$docs" | jq --arg path "$path" '[
        .[] |
        select(.kind == "HorizontalPodAutoscaler") |
        {
            name: .metadata.name,
            namespace: (.metadata.namespace // "default"),
            path: $path,
            target_workload: .spec.scaleTargetRef.name,
            min_replicas: (.spec.minReplicas // 1),
            max_replicas: .spec.maxReplicas
        }
    ]')
    
    # Output JSON with all data
    jq -n \
        --argjson manifest "$manifest" \
        --argjson workloads "$workloads_with_containers" \
        --argjson pdbs "$pdbs" \
        --argjson hpas "$hpas" \
        '{manifest: $manifest, workloads: $workloads, pdbs: $pdbs, hpas: $hpas}'
}

export -f process_file
export -f is_helm_template
export WORKLOAD_KINDS

# Command to find K8s manifests (from input or default)
FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-git ls-files '*.yaml' '*.yml'}"

# Build exclusion pattern for directories
DIR_PATTERN="(^|/)($(IFS='|'; echo "${IGNORE_DIRS[*]}"))(/|$)"
FILE_PATTERN="($(IFS='|'; echo "${IGNORE_FILES[*]}"))$"

# Process files in parallel and aggregate results
results=$(eval "$FIND_CMD" 2>/dev/null | \
    grep -vE "$DIR_PATTERN" | \
    grep -vE "$FILE_PATTERN" | \
    parallel -j 4 process_file 2>/dev/null | \
    jq -s '{
        manifests: [.[].manifest | select(. != null)],
        workloads: [.[].workloads[] | select(. != null)],
        pdbs: [.[].pdbs[] | select(. != null)],
        hpas: [.[].hpas[] | select(. != null)]
    }')

# Calculate summary
summary=$(echo "$results" | jq '{
    all_valid: ([.manifests[].valid] | all),
    all_have_resources: ([.workloads[].containers[].has_resources] | if length == 0 then true else all end),
    all_have_probes: ([.workloads[].containers[] | (.has_liveness_probe and .has_readiness_probe)] | if length == 0 then true else all end),
    all_non_root: ([.workloads[].containers[].runs_as_non_root] | if length == 0 then true else all end),
    all_have_pdb: (
        [.workloads[] | "\(.namespace)/\(.name)"] as $workload_keys |
        [.pdbs[] | "\(.namespace)/\(.target_workload)"] as $pdb_keys |
        ($workload_keys | length == 0) or ($workload_keys | all(. as $w | $pdb_keys | contains([$w])))
    )
}')

# Combine and collect
echo "$results" | jq --argjson summary "$summary" '. + {summary: $summary}' | lunar collect -j ".k8s" -

# Submit source metadata
TOOL_VERSION=$(kubeconform -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
jq -n --arg tool "kubeconform" --arg version "$TOOL_VERSION" \
    '{tool: $tool, version: $version}' | lunar collect -j ".k8s.source" -

