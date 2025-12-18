#!/bin/bash

set -e

# Function to process a single Terraform file
process_file() {
  local tf_file="$1"
  local rel_path="${tf_file#./}"

  # Try to parse the file with hcl2json
  set +e
  json_output="$(hcl2json "$tf_file" 2>&1)"
  status=$?
  set -e

  if [ $status -eq 0 ]; then
    # File is valid
    valid=true
    error=null
    json_content="$json_output"
  else
    # File has syntax errors
    valid=false
    error="$json_output"
    json_content='{}'
  fi

  # Build JSON object for this file
  obj="$(
    jq -n \
      --arg terraform_file_location "$rel_path" \
      --argjson valid "$valid" \
      --argjson json_content "$json_content" \
      --arg error "$error" \
      '{
        terraform_file_location: $terraform_file_location,
        valid: $valid,
        json_content: $json_content
      } + (if $error == "null" then {} else {error: $error} end)'
  )"

  # Output the JSON object
  echo "$obj"
}

# Export function for parallel processing
export -f process_file

# Find all .tf files and process them
find . -type f -name '*.tf' | \
  parallel -j 4 process_file | \
  jq -s '{files: .}' | \
  lunar collect -j ".terraform" -

# Use helper functions to check for certain properties in the Terraform files.
# Only run these checks if we have valid files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/check_internet_access.sh"
source "$SCRIPT_DIR/check_waf.sh"
source "$SCRIPT_DIR/check_datastores.sh"

# Create a temporary file with only valid terraform files for the checks
valid_tf_objects="valid_tf_objects.json"
find . -type f -name '*.tf' | while read -r tf_file; do
  if hcl2json "$tf_file" >/dev/null 2>&1; then
    rel_path="${tf_file#./}"
    json=$(hcl2json "$tf_file")
    printf "{\"path\":\"%s\", \"json\": %s}\n" "$rel_path" "$json"
  fi
done > "$valid_tf_objects"

# Only run checks if we have valid files
if [ -s "$valid_tf_objects" ]; then
  # These calls check if the service is internet accessible and has WAF protection
  is_public=$(check_internet_accessibility "$valid_tf_objects")
  has_waf_protection=$(check_waf_protection "$valid_tf_objects")

  # This call checks if the service has any datastores and if they have prevent_destroy protection
  datastore_info=$(check_datastore_info "$valid_tf_objects")
  has_datastores=$(echo "$datastore_info" | jq -r '.has_datastores')
  has_datastore_protection=$(echo "$datastore_info" | jq -r '.has_protection')
  unprotected_resources_json=$(echo "$datastore_info" | jq '.unprotected_resources')

  # Collect all of the results that describe the properties of the Terraform configured
  lunar collect -j ".terraform.is_internet_accessible" "$is_public"
  lunar collect -j ".terraform.has_waf_protection" "$has_waf_protection"
  lunar collect -j ".terraform.has_datastores" "$has_datastores"
  lunar collect -j ".terraform.has_datastore_protection" "$has_datastore_protection"
  lunar collect -j ".terraform.unprotected_datastores" "$unprotected_resources_json"
fi