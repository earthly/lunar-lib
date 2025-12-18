#!/bin/bash

# List of suppoerted data store resource types
DATASTORE_TYPES="aws_s3_bucket \
    aws_db_instance \
    aws_dynamodb_table \
    aws_elasticache_cluster \
    aws_elasticache_replication_group \
    aws_ebs_volume \
    aws_efs_file_system \
    aws_secretsmanager_secret \
    aws_ssm_parameter \
    aws_cloudwatch_log_group"

# Combined function to check both existence and destroy protection of data store resources
check_datastore_info() {
    local objects_file="$1"
    
    local has_datastores=false
    local has_protection=true  # Start optimistic - assume all are protected
    local unprotected_resources=""
    
    for resource_type in $DATASTORE_TYPES; do
        # Check if this resource type exists in the Terraform
        local has_resource=$(jq -r -s "any(.[]; ((.json? // {} | .resource? // {} | .$resource_type // {}) | length > 0))" "$objects_file")
        
        if [ "$has_resource" = "true" ]; then
            has_datastores=true
            
            # Get list of unprotected resources for this type
            local unprotected_for_type=$(jq -r -s --arg resource_type "$resource_type" '
                [.[] | 
                    (.json? // {} | .resource? // {} | .[$resource_type] // {} | to_entries | 
                    [.[] | select(.value[0] | (.lifecycle? // [] | .[0]? // {} | .prevent_destroy // false) != true) | 
                    .key])] | 
                flatten | 
                join(", ")
            ' "$objects_file")
            
            # Collect the unprotected resources for this type
            # Format is: "resource_type.resource_name" (e.g. "aws_s3_bucket.my_data")
            if [ -n "$unprotected_for_type" ] && [ "$unprotected_for_type" != "" ]; then
                has_protection=false
                if [ -n "$unprotected_resources" ]; then
                    unprotected_resources="$unprotected_resources, \"$resource_type.$unprotected_for_type\""
                else
                    unprotected_resources="\"$resource_type.$unprotected_for_type\""
                fi
            fi
        fi
    done
    
    # Return as structured JSON so the caller can access each field separately
    jq -n --arg has_datastores "$has_datastores" --arg has_protection "$has_protection" --argjson unprotected_resources "[$unprotected_resources]" \
        '{has_datastores: $has_datastores, has_protection: $has_protection, unprotected_resources: $unprotected_resources}'
}
