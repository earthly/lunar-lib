#!/bin/bash

set -e

# Configuration from inputs (LUNAR_VAR_ prefix)
RULES="${LUNAR_VAR_RULES:-}"
EXCLUDE_PATHS="${LUNAR_VAR_EXCLUDE_PATHS:-vendor,node_modules,.git,dist,build}"
MAX_MATCHES="${LUNAR_VAR_MAX_MATCHES_PER_RULE:-100}"
DEBUG="${LUNAR_VAR_DEBUG:-false}"

# Debug helper
debug() {
    if [ "$DEBUG" = "true" ]; then
        echo "DEBUG: $*" >&2
    fi
}

# Check if rules are provided
if [ -z "$RULES" ]; then
    echo "Error: No rules provided. Set the 'rules' input with ast-grep YAML rules." >&2
    exit 1
fi

# Create temp file for rules (BusyBox-compatible)
RULES_FILE=$(mktemp -t ast-grep-rules-XXXXXX)
mv "$RULES_FILE" "${RULES_FILE}.yml"
RULES_FILE="${RULES_FILE}.yml"
trap "rm -f '$RULES_FILE'" EXIT

# Write rules to temp file
echo "$RULES" > "$RULES_FILE"

debug "ast-grep version: $(ast-grep --version 2>/dev/null || echo 'unknown')"
debug "Rules file content:"
if [ "$DEBUG" = "true" ]; then
    cat "$RULES_FILE" >&2
fi

# Build exclusion arguments for ast-grep
# ast-grep uses --globs for file patterns
EXCLUDE_ARGS=""
IFS=',' read -ra EXCLUDE_ARRAY <<< "$EXCLUDE_PATHS"
for path in "${EXCLUDE_ARRAY[@]}"; do
    path=$(echo "$path" | xargs)  # trim whitespace
    if [ -n "$path" ]; then
        EXCLUDE_ARGS="$EXCLUDE_ARGS --globs !${path}/**"
    fi
done

debug "Exclude args: $EXCLUDE_ARGS"
debug "Running: ast-grep scan --rule $RULES_FILE --json . $EXCLUDE_ARGS"

# Run ast-grep and capture output
SG_OUTPUT=$(ast-grep scan --rule "$RULES_FILE" --json . $EXCLUDE_ARGS 2>/dev/null || true)

debug "Raw ast-grep output:"
if [ "$DEBUG" = "true" ]; then
    echo "$SG_OUTPUT" >&2
fi

# If no output or empty array, create empty result
if [ -z "$SG_OUTPUT" ] || [ "$SG_OUTPUT" = "[]" ] || [ "$SG_OUTPUT" = "null" ]; then
    SG_OUTPUT="[]"
fi

# Process the output with jq to:
# 1. Group matches by ruleId
# 2. Split ruleId on '.' to get category and subcategory
# 3. Build the Component JSON structure
# 4. Apply max_matches limit
RESULT=$(echo "$SG_OUTPUT" | jq --argjson max_matches "$MAX_MATCHES" '
# Group matches by ruleId
group_by(.ruleId) |

# Transform each group into the desired structure
map({
    ruleId: .[0].ruleId,
    message: .[0].message,
    severity: .[0].severity,
    count: length,
    matches: (.[0:$max_matches] | map({
        file: .file,
        range: .range,
        code: .text
    }))
}) |

# Build nested structure from ruleId (category.subcategory)
reduce .[] as $rule ({};
    ($rule.ruleId | split(".")) as $parts |
    if ($parts | length) >= 2 then
        .[$parts[0]][$parts[1]] = {
            count: $rule.count,
            message: $rule.message,
            severity: $rule.severity,
            matches: $rule.matches
        }
    else
        # If no dot in ruleId, put under "custom" category
        .custom[$rule.ruleId] = {
            count: $rule.count,
            message: $rule.message,
            severity: $rule.severity,
            matches: $rule.matches
        }
    end
)
')

# Get ast-grep version
SG_VERSION=$(ast-grep --version 2>/dev/null | head -1 | awk '{print $2}' || echo "unknown")

# Add source metadata
FINAL_OUTPUT=$(echo "$RESULT" | jq --arg version "$SG_VERSION" '{
    source: {
        tool: "ast-grep",
        version: $version
    }
} + .')

# Write to Component JSON
echo "$FINAL_OUTPUT" | lunar collect -j ".code_patterns" -
