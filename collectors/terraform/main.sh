#!/bin/bash
set -e

# Process a single .tf file — output JSON with path, validity, and parsed HCL
process_file() {
    local tf_file="$1"
    local rel_path="${tf_file#./}"

    set +e
    hcl_json="$(hcl2json "$tf_file" 2>&1)"
    status=$?
    set -e

    if [ $status -eq 0 ]; then
        jq -n --arg path "$rel_path" --argjson hcl "$hcl_json" \
            '{path: $path, valid: true, hcl: $hcl}'
    else
        jq -n --arg path "$rel_path" --arg error "$hcl_json" \
            '{path: $path, valid: false, error: $error}'
    fi
}
export -f process_file

# Find all .tf files
tf_files=$(find . -type f -name '*.tf' 2>/dev/null)
if [ -z "$tf_files" ]; then
    exit 0
fi

# Process in parallel
all_results=$(echo "$tf_files" | parallel -j 4 process_file | jq -s '.')

# Write .iac.files[] — {path, valid, error?}
echo "$all_results" | jq '[.[] | {path, valid} + (if .error then {error} else {} end)]' \
    | lunar collect -j ".iac.files" -

# Write .iac.native.terraform.files[] — {path, hcl} for valid files only
echo "$all_results" | jq '[.[] | select(.valid) | {path, hcl}]' \
    | lunar collect -j ".iac.native.terraform.files" -

# Write source metadata
TOOL_VERSION=$(cat /usr/local/bin/hcl2json.version 2>/dev/null || echo "unknown")
jq -n --arg version "$TOOL_VERSION" '{tool: "hcl2json", version: $version}' \
    | lunar collect -j ".iac.source" -
