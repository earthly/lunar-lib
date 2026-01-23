#!/bin/bash

set -e

# Configuration from inputs (uppercase env vars)
RULES="${RULES:-}"
EXCLUDE_PATHS="${EXCLUDE_PATHS:-vendor,node_modules,.git,dist,build}"
MAX_MATCHES="${MAX_MATCHES_PER_RULE:-100}"

# Check if rules are provided
if [ -z "$RULES" ]; then
    echo "Error: No rules provided. Set the 'rules' input with ast-grep YAML rules." >&2
    exit 1
fi

# Create temp file for rules
RULES_FILE=$(mktemp --suffix=.yml)
trap "rm -f '$RULES_FILE'" EXIT

# Write rules to temp file
echo "$RULES" > "$RULES_FILE"

# Build exclusion arguments for sg
EXCLUDE_ARGS=""
IFS=',' read -ra EXCLUDE_ARRAY <<< "$EXCLUDE_PATHS"
for path in "${EXCLUDE_ARRAY[@]}"; do
    path=$(echo "$path" | xargs)  # trim whitespace
    if [ -n "$path" ]; then
        EXCLUDE_ARGS="$EXCLUDE_ARGS --no-ignore-vcs --globs !$path/**"
    fi
done

# Run ast-grep and capture output
# Note: sg scan returns exit code 0 even with matches
SG_OUTPUT=$(sg scan --rule "$RULES_FILE" --json . $EXCLUDE_ARGS 2>/dev/null || true)

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
SG_VERSION=$(sg --version 2>/dev/null | head -1 | awk '{print $2}' || echo "unknown")

# Add source metadata
FINAL_OUTPUT=$(echo "$RESULT" | jq --arg version "$SG_VERSION" '{
    source: {
        tool: "ast-grep",
        version: $version
    }
} + .')

# Write to Component JSON
echo "$FINAL_OUTPUT" | lunar collect -j ".code_patterns" -
