#!/bin/bash
# Collects Istio service-mesh configuration from repository manifests.
# Parses Istio custom resources (traffic, security, telemetry, install) plus
# sidecar-injection settings, validates them offline with `istioctl analyze`,
# and writes the normalized posture to the tool-agnostic .mesh category.
set -e

HERE="$(dirname "$0")"
# shellcheck source=/dev/null
source "$HERE/helm.sh"

# Directories and files to ignore (mirrors the k8s collector).
IGNORE_DIRS=(".github" ".git" "node_modules" "vendor" "templates" "charts" "helm" "openapi")
IGNORE_FILES=("catalog-info.yaml" "catalog-info.yml" "Chart.yaml" "Chart.yml")

# Command to find candidate manifest files (from input or default).
FIND_CMD="${LUNAR_VAR_FIND_COMMAND:-find . -type f \( -name '*.yaml' -o -name '*.yml' \)}"

DIR_PATTERN="(^|/)($(IFS='|'; echo "${IGNORE_DIRS[*]}"))(/|$)"
FILE_PATTERN="($(IFS='|'; echo "${IGNORE_FILES[*]}"))$"

CHUNKS_FILE=/tmp/istio_chunks.jsonl
: > "$CHUNKS_FILE"
ISTIO_FILES=()

# --- Phase 1: structural extraction, one file at a time -----------------------
# Istio configs are a small subset of a repo, so we pre-filter cheaply on the
# literal string "istio" before doing the (more expensive) YAML parse.
while IFS= read -r f; do
    [ -f "$f" ] || continue
    path="${f#./}"
    content="$(cat "$f")"

    # Fast pre-filter: every Istio apiVersion and injection label contains "istio".
    echo "$content" | grep -q 'istio' || continue

    # Skip Helm templates — they aren't valid standalone YAML.
    if is_helm_template "$content"; then
        continue
    fi

    # Parse (possibly multi-document) YAML into a JSON array.
    docs=$(echo "$content" | yq -o=json '.' 2>/dev/null | jq -s '.' 2>/dev/null || echo '[]')
    [ "$docs" = "[]" ] && continue

    chunk=$(echo "$docs" | jq -c --arg path "$path" -f "$HERE/parse.jq" 2>/dev/null || echo '')
    [ -z "$chunk" ] && continue

    signal=$(echo "$chunk" | jq '.istio_signal // 0' 2>/dev/null || echo 0)
    if [ "${signal:-0}" -gt 0 ]; then
        echo "$chunk" >> "$CHUNKS_FILE"
        ISTIO_FILES+=("$path")
    fi
done < <(eval "$FIND_CMD" 2>/dev/null | grep -vE "$DIR_PATTERN" | grep -vE "$FILE_PATTERN")

# Nothing Istio-related found — write nothing so policies skip cleanly.
if [ ! -s "$CHUNKS_FILE" ]; then
    echo "istio: no Istio resources found — skipping" >&2
    exit 0
fi

# --- Phase 2: validate offline with istioctl analyze --------------------------
# Two failure signals: schema/parse errors go to stderr ("error processing
# <file>[n]: ..."), semantic issues appear as level=Error messages in -o json.
# Exit code is unreliable in --use-kube=false mode, so we parse both streams.
VALIDITY='{}'
if command -v istioctl >/dev/null 2>&1 && [ "${#ISTIO_FILES[@]}" -gt 0 ]; then
    istioctl analyze --use-kube=false -o json "${ISTIO_FILES[@]}" \
        >/tmp/istio_analyze.json 2>/tmp/istio_analyze.err || true

    VALIDITY_FILE=/tmp/istio_validity.jsonl
    : > "$VALIDITY_FILE"

    # Schema/parse errors (stderr).
    if [ -s /tmp/istio_analyze.err ]; then
        grep 'error processing ' /tmp/istio_analyze.err 2>/dev/null | while IFS= read -r line; do
            p=$(echo "$line" | sed -n 's/.*error processing \([^[]*\)\[[0-9]*\]:.*/\1/p')
            msg=$(echo "$line" | sed -n 's/.*error processing [^:]*: \(.*\)/\1/p')
            [ -z "$p" ] && continue
            jq -cn --arg p "$p" --arg m "istioctl analyze: ${msg:-schema validation failed}" '{($p): $m}'
        done >> "$VALIDITY_FILE" || true
    fi

    # Semantic Error-level messages (-o json), best effort — the reference field
    # is "path:line:col"; take the path prefix.
    if jq -e 'type == "array"' /tmp/istio_analyze.json >/dev/null 2>&1; then
        jq -c '.[] | select(.level == "Error")
               | ((.reference // .documentReference // "") | split(":")[0]) as $p
               | select($p != "") | {($p): (.message // "istioctl analyze reported an error")}' \
            /tmp/istio_analyze.json 2>/dev/null >> "$VALIDITY_FILE" || true
    fi

    VALIDITY=$(jq -cs 'add // {}' "$VALIDITY_FILE" 2>/dev/null || echo '{}')
fi

# --- Phase 3: aggregate and collect -------------------------------------------
CHUNKS=$(jq -cs '.' "$CHUNKS_FILE")
MESH=$(jq -cn --argjson chunks "$CHUNKS" --argjson validity "$VALIDITY" \
    '{chunks: $chunks, validity: $validity}' | jq -c -f "$HERE/aggregate.jq")

echo "$MESH" | lunar collect -j ".mesh" -

# Source metadata (separate merge, mirrors the k8s collector).
IVERSION=$(istioctl version --remote=false 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")
jq -n --arg tool "istio" --arg version "${IVERSION:-unknown}" \
    '{tool: $tool, version: $version, integration: "code"}' | lunar collect -j ".mesh.source" -
