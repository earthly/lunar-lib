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

    jq -n -c \
        --arg name "$name" \
        --arg ref "$ref" \
        --arg pinning "$pinning" \
        --arg party "$party" \
        --arg uses "$uses" \
        '{name: $name, ref: $ref, pinning: $pinning, party: $party, uses: $uses}'
}

# ── Parse workflows ─────────────────────────────────────────────────────────
# Accumulate into files rather than shell variables. jq's --argjson passes a
# value as a single argv element, and the kernel caps that at 128 KiB
# (MAX_ARG_STRLEN) regardless of ulimit -s — a large monorepo's projection
# exceeds it and jq fails to exec with "Argument list too long". Files are read
# by path, so they have no such limit, and appending is O(1) instead of piping
# the whole accumulated array back through jq once per item.
WORKFLOWS_FILE="/tmp/gha-workflows.json"
ALL_DEPS_FILE="/tmp/gha-deps.json"
WF_ACTIONS_FILE="/tmp/gha-workflow-actions.json"
: > "$WORKFLOWS_FILE"
: > "$ALL_DEPS_FILE"

while IFS= read -r file; do
    [ -z "$file" ] && continue

    # Convert YAML to JSON once with yq, then use jq for all querying
    wf_json=$(yq -o json "$file" 2>/dev/null || echo '{}')

    wf_name=$(echo "$wf_json" | jq -r '.name // ""' 2>/dev/null || echo "")

    # Handle 'on' field (can be string, array, or object)
    triggers=$(echo "$wf_json" | jq -c '
        .on | if type == "string" then [.]
        elif type == "array" then .
        elif type == "object" then [keys[]]
        else [] end
    ' 2>/dev/null || echo '[]')

    # Extract full job details for native data
    jobs_detail=$(echo "$wf_json" | jq -c '
        if .jobs then
            .jobs | to_entries | map({
                key: .key,
                value: (
                    (if .value.permissions then {permissions: .value.permissions} else {} end)
                    + (if .value.uses then {uses: .value.uses} else {} end)
                    + (if .value.secrets then {secrets: .value.secrets} else {} end)
                    + {steps: [(.value.steps // [])[] |
                        {name, uses, run, "with": .["with"], env}
                        | with_entries(select(.value != null))
                    ]}
                )
            }) | from_entries
        else
            {}
        end
    ' 2>/dev/null || echo '{}')

    # Extract workflow-level permissions
    permissions=$(echo "$wf_json" | jq -c '.permissions // null' 2>/dev/null || echo 'null')

    # Extract all uses: references from job steps and reusable workflow calls
    uses_refs=$(echo "$wf_json" | jq -c '
        [
            (.jobs[]?.steps[]? | select(.uses) | .uses),
            (.jobs[]? | select(.uses) | .uses)
        ]
    ' 2>/dev/null || echo '[]')

    # Classify each action
    : > "$WF_ACTIONS_FILE"
    for uses in $(echo "$uses_refs" | jq -r '.[]' 2>/dev/null); do
        action_json=$(classify_action "$uses")
        if [ -n "$action_json" ]; then
            printf '%s\n' "$action_json" >> "$WF_ACTIONS_FILE"
            printf '%s\n' "$action_json" >> "$ALL_DEPS_FILE"
        fi
    done

    # Build workflow object. $jobs_detail is the one value here that grows with
    # the workflow's size, so it goes on stdin; the classified actions are a
    # stream of objects in their own file, which --slurpfile reads as an array.
    printf '%s' "$jobs_detail" | jq -c \
        --arg file "$file" \
        --arg name "$wf_name" \
        --argjson triggers "$triggers" \
        --argjson permissions "$permissions" \
        --slurpfile actions "$WF_ACTIONS_FILE" \
        '{
            file: $file,
            name: $name,
            triggers: $triggers,
            jobs: .,
            permissions: $permissions,
            actions: $actions
        }' >> "$WORKFLOWS_FILE"
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

# ── Write normalized .ci.lint ───────────────────────────────────────────────
# $LINT_ERRORS grows with the number of actionlint findings, so it goes on
# stdin; only the scalars stay on argv.
printf '%s' "$LINT_ERRORS" | jq \
    --argjson error_count "$ERROR_COUNT" \
    --argjson warning_count "$WARNING_COUNT" \
    --arg tool "actionlint" \
    --arg version "$ACTIONLINT_VERSION" \
    '{
        source: {tool: $tool, version: $version, integration: "code"},
        errors: .,
        error_count: $error_count,
        warning_count: $warning_count
    }' | lunar collect -j ".ci.lint" -

# ── Write normalized .ci.dependencies ───────────────────────────────────────
# -s slurps the dependency stream into an array; the counts are derived from it
# here so nothing repo-sized has to cross argv.
jq -s '. as $items | {
        source: {tool: "github-actions", version: "0.1.0", integration: "code"},
        total: ($items | length),
        pinned: ($items | map(select(.pinning == "sha" or .pinning == "tag")) | length),
        unpinned: ($items | map(select(.pinning == "branch" or .pinning == "unpinned")) | length),
        items: $items,
        third_party_unpinned: [
            $items[]
            | select(.party == "3rd" and (.pinning == "branch" or .pinning == "unpinned"))
            | .uses
        ]
    }' "$ALL_DEPS_FILE" | lunar collect -j ".ci.dependencies" -

# ── Write native .ci.native.github_actions ──────────────────────────────────
jq -s '{
        source: {tool: "github-actions", version: "0.1.0", integration: "code"},
        workflows: .
    }' "$WORKFLOWS_FILE" | lunar collect -j ".ci.native.github_actions" -
