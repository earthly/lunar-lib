#!/bin/bash

# Function to check if services are internet accessible
check_internet_accessibility() {
    local objects_file="$1"
    
    # Check for various types of internet-accessible resources
    local has_alb_public=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_lb // {} | to_entries | [ .[].value[]? ]) | any(.[]; (.scheme // "") == "internet-facing")))' "$objects_file")
    local has_elb_public=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_elb // {} | to_entries | [ .[].value[]? ]) | any(.[]; ((.internal // false) == false))))' "$objects_file")
    local has_apigw_public=$(jq -r -s 'any(.[]; (((.json? // {} | .resource? // {} | .aws_api_gateway_rest_api // {}) | length > 0) or ((.json? // {} | .resource? // {} | .aws_apigatewayv2_api // {}) | length > 0)))' "$objects_file")
    local has_cloudfront=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_cloudfront_distribution // {}) | length > 0))' "$objects_file")
    local has_ec2_public_ip=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_instance // {} | to_entries | [ .[].value[]? ]) | any(.[]; (.associate_public_ip_address // false) == true)))' "$objects_file")
    local has_s3_website=$(jq -r -s 'any(.[]; ( ((.json? // {} | .resource? // {} | .aws_s3_bucket_website_configuration // {}) | length > 0) or (((.json? // {} | .resource? // {} | .aws_s3_bucket // {} | to_entries | [ .[].value[]? ]) | any(.[]; ((.website // []) | length > 0)))) ))' "$objects_file")
    local has_open_sg=$(jq -r -s 'any(.[]; ((.json? // {} | .resource? // {} | .aws_security_group // {} | to_entries | [ .[].value[]? ])
      | any(.[];
          any(.ingress[]?;
            (
              ((.cidr_blocks? // []) | (if type=="array" then . else [.] end) | any(.=="0.0.0.0/0"))
              or
              ((.ipv6_cidr_blocks? // []) | (if type=="array" then . else [.] end) | any(.=="::/0"))
            )
          )
        )
      ))' "$objects_file")
    
    # Determine if any service is internet accessible
    local is_public=false
    {
        [ "$has_alb_public" = "true" ] || \
        [ "$has_elb_public" = "true" ] || \
        [ "$has_apigw_public" = "true" ] || \
        [ "$has_cloudfront" = "true" ] || \
        [ "$has_ec2_public_ip" = "true" ] || \
        [ "$has_s3_website" = "true" ] || \
        [ "$has_open_sg" = "true" ]
    } && is_public=true
    
    echo "$is_public"
}