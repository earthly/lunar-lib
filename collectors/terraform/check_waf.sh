#!/bin/bash

# Function to check if WAF protection is present and properly configured
check_waf_protection() {
    local objects_file="$1"
    
    # WAF detection heuristics
    local has_wafv2=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_wafv2_web_acl // {}) | length > 0))' "$objects_file")
    local has_waf_association=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_wafv2_web_acl_association // {}) | length > 0))' "$objects_file")
    local has_cloudfront_waf=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_cloudfront_distribution // {} | to_entries | [ .[].value[]? ]) | any(.[]; (.web_acl_id // "") != "")))' "$objects_file")
    
    # Check if WAF is present and associated with internet-facing services
    local has_waf_protection=false
    {
        [ "$has_wafv2" = "true" ] && [ "$has_waf_association" = "true" ] || \
        [ "$has_cloudfront_waf" = "true" ]
    } && has_waf_protection=true
    
    echo "$has_waf_protection"
}
