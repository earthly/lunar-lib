#!/bin/bash
set -e

# ── Early exit if no GHA workflows ──────────────────────────────────────────
if [ ! -d ".github/workflows" ]; then
    echo "No .github/workflows/ directory found" >&2
    exit 0
fi

WORKFLOW_FILES=$(find .github/workflows -maxdepth 1 \( -name '*.yml' -o -name '*.yaml' \) -type f 2>/dev/null | sort)
if [ -z "$WORKFLOW_FILES" ]; then
    echo "No workflow files found in .github/workflows/" >&2
    exit 0
fi

# ── Detect repo org for 1st/3rd party classification ────────────────────────
REPO_ORG=""
if [ -n "$LUNAR_COMPONENT_ID" ]; then
    REPO_ORG=$(echo "$LUNAR_COMPONENT_ID" | sed 's|github\.com/||' | cut -d'/' -f1)
fi
if [ -z "$REPO_ORG" ]; then
    REPO_ORG=$(git remote get-url origin 2>/dev/null | sed -E 's|.*[:/]([^/]+)/[^/]+(.git)?$|\1|' || true)
fi

# ── Classify action pinning ─────────────────────────────────────────────────
classify_action() {
    local uses="$1"
    local name ref pinning party

    # Docker or local actions — skip
    if [[ "$uses" == docker://* ]] || [[ "$uses" == ./* ]] || [[ "$uses" == ../* ]]; then
        return
    fi

    # Split on @
    name="${uses%%@*}"
    ref="${uses#*@}"

    # No @ means unpinned
    if [ "$name" = "$uses" ]; then
        ref=""
        pinning="unpinned"
    elif echo "$ref" | grep -qE '^[a-f0-9]{40}'; then
        pinning="sha"
    elif echo "$ref" | grep -qE '^v?[0-9]+(\.[0-9]+)*'; then
        pinning="tag"
    else
        pinning="branch"
    fi

    # 1st-party = same org
    local action_org="${name%%/*}"
    if [ -n "$REPO_ORG" ] && [ "$action_org" = "$REPO_ORG" ]; then
        party="1st"
    else
        party="3rd"
    fi

    jq -n \
        --arg name "$name" \
        --arg ref "$ref" \
        --arg pinning "$pinning" \
        --arg party "$party" \
        --arg uses "$uses" \
        '{name: $name, ref: $ref, pinning: $pinning, party: $party, uses: $uses}'
}

# ── Parse workflows ─────────────────────────────────────────────────────────
WORKFLOWS="[]"
ALL_DEPS="[]"

while IFS= read -r file; do
    [ -z "$file" ] && continue

    # Extract workflow metadata with yq
    wf_name=$(yq -r '.name // ""' "$file" 2>/dev/null || echo "")

    # Handle 'on' field (can be string, array, or object)
    triggers=$(yq -c '
        .on | if type == "string" then [.]
        elif type == "array" then .
        elif type == "object" then [keys[]]
        else [] end
    ' "$file" 2>/dev/null || echo '[]')

    # Extract job names
    jobs=$(yq -c '[.jobs | keys[]]' "$file" 2>/dev/null || echo '[]')

    # Extract workflow-level permissions
    permissions=$(yq -c '.permissions // null' "$file" 2>/dev/null)

    # Extract all uses: references from job steps and reusable workflow calls
    uses_refs=$(yq -c '
        [
            (.jobs[]?.steps[]? | select(.uses) | .uses),
            (.jobs[]? | select(.uses) | .uses)
        ]
    ' "$file" 2>/dev/null || echo '[]')

    # Classify each action
    ACTIONS="[]"
    for uses in $(echo "$uses_refs" | jq -r '.[]' 2>/dev/null); do
        action_json=$(classify_action "$uses")
        if [ -n "$action_json" ]; then
            ACTIONS=$(echo "$ACTIONS" | jq --argjson a "$action_json" '. + [$a]')
            ALL_DEPS=$(echo "$ALL_DEPS" | jq --argjson a "$action_json" '. + [$a]')
        fi
    done

    # Build workflow object
    WORKFLOW=$(jq -n \
        --arg file "$file" \
        --arg name "$wf_name" \
        --argjson triggers "$triggers" \
        --argjson jobs "$jobs" \
        --argjson permissions "$permissions" \
        --argjson actions "$ACTIONS" \
        '{
            file: $file,
            name: $name,
            triggers: $triggers,
            jobs: $jobs,
            permissions: $permissions,
            actions: $actions
        }')

    WORKFLOWS=$(echo "$WORKFLOWS" | jq --argjson w "$WORKFLOW" '. + [$w]')
done <<< "$WORKFLOW_FILES"

# ── Run actionlint ──────────────────────────────────────────────────────────
LINT_ERRORS="[]"
ERROR_COUNT=0
WARNING_COUNT=0

if command -v actionlint &>/dev/null; then
    ACTIONLINT_VERSION=$(actionlint --version 2>/dev/null | head -1 || echo "unknown")

    # actionlint -format outputs one JSON per error, exits 1 if errors found
    LINT_RAW=$(actionlint -format '{{json .}}' 2>&1 || true)

    if [ -n "$LINT_RAW" ]; then
        LINT_ERRORS=$(echo "$LINT_RAW" | jq -s '[.[] | {
            file: .filepath,
            line: .line,
            column: .column,
            message: .message,
            rule: .kind
        }]' 2>/dev/null || echo '[]')
        ERROR_COUNT=$(echo "$LINT_ERRORS" | jq 'length')
    fi
else
    ACTIONLINT_VERSION="not-installed"
    echo "actionlint not found, skipping lint" >&2
fi

# ── Build pinning summary ──────────────────────────────────────────────────
TOTAL=$(echo "$ALL_DEPS" | jq 'length')
SHA_PINNED=$(echo "$ALL_DEPS" | jq '[.[] | select(.pinning == "sha")] | length')
TAG_PINNED=$(echo "$ALL_DEPS" | jq '[.[] | select(.pinning == "tag")] | length')
BRANCH_REF=$(echo "$ALL_DEPS" | jq '[.[] | select(.pinning == "branch")] | length')
UNPINNED=$(echo "$ALL_DEPS" | jq '[.[] | select(.pinning == "unpinned")] | length')
PINNED=$((SHA_PINNED + TAG_PINNED))
NOT_PINNED=$((BRANCH_REF + UNPINNED))
THIRD_PARTY_UNPINNED=$(echo "$ALL_DEPS" | jq -c '[.[] | select(.party == "3rd" and (.pinning == "branch" or .pinning == "unpinned")) | .uses]')

# ── Write normalized .ci.lint ───────────────────────────────────────────────
jq -n \
    --argjson errors "$LINT_ERRORS" \
    --argjson error_count "$ERROR_COUNT" \
    --argjson warning_count "$WARNING_COUNT" \
    --arg tool "actionlint" \
    --arg version "$ACTIONLINT_VERSION" \
    '{
        source: {tool: $tool, version: $version, integration: "code"},
        errors: $errors,
        error_count: $error_count,
        warning_count: $warning_count
    }' | lunar collect -j ".ci.lint" -

# ── Write normalized .ci.dependencies ───────────────────────────────────────
jq -n \
    --argjson total "$TOTAL" \
    --argjson pinned "$PINNED" \
    --argjson unpinned "$NOT_PINNED" \
    --argjson items "$ALL_DEPS" \
    --argjson third_party_unpinned "$THIRD_PARTY_UNPINNED" \
    '{
        source: {tool: "github-actions", version: "0.1.0", integration: "code"},
        total: $total,
        pinned: $pinned,
        unpinned: $unpinned,
        items: $items,
        third_party_unpinned: $third_party_unpinned
    }' | lunar collect -j ".ci.dependencies" -

# ── Write native .ci.native.github_actions ──────────────────────────────────
jq -n \
    --argjson workflows "$WORKFLOWS" \
    '{
        source: {tool: "github-actions", version: "0.1.0", integration: "code"},
        workflows: $workflows
    }' | lunar collect -j ".ci.native.github_actions" -
