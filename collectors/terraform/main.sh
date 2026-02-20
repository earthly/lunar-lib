#!/bin/bash
set -e

# --- Resource category mapping ---
DATASTORE_TYPES="aws_s3_bucket aws_db_instance aws_dynamodb_table aws_elasticache_cluster aws_elasticache_replication_group aws_ebs_volume aws_efs_file_system aws_rds_cluster aws_redshift_cluster"
COMPUTE_TYPES="aws_instance aws_ecs_service aws_lambda_function aws_autoscaling_group aws_ecs_cluster aws_eks_cluster"
NETWORK_TYPES="aws_lb aws_elb aws_security_group aws_api_gateway_rest_api aws_apigatewayv2_api aws_cloudfront_distribution aws_route53_zone"
SECURITY_TYPES="aws_wafv2_web_acl aws_wafv2_web_acl_association aws_kms_key"

# --- Parse a single .tf file ---
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

# --- Find all .tf files ---
tf_files=$(find . -type f -name '*.tf' 2>/dev/null)
if [ -z "$tf_files" ]; then
    exit 0
fi

# --- Process all files ---
all_results=$(echo "$tf_files" | parallel -j 4 process_file | jq -s '.')

# --- Write .iac.files[] (validity) ---
echo "$all_results" | jq '[.[] | {path, valid} + (if .error then {error} else {} end)]' \
    | lunar collect -j ".iac.files" -

# --- Write .iac.native.terraform.files[] (raw HCL for terraform-specific policy) ---
echo "$all_results" | jq '[.[] | select(.valid) | {path, hcl}]' \
    | lunar collect -j ".iac.native.terraform.files" -

# --- Build normalized .iac.modules[] ---
echo "$all_results" | jq --arg DS "$DATASTORE_TYPES" --arg CO "$COMPUTE_TYPES" \
    --arg NE "$NETWORK_TYPES" --arg SE "$SECURITY_TYPES" '

def categorize(rtype):
    if ($DS | split(" ") | index(rtype)) then "datastore"
    elif ($CO | split(" ") | index(rtype)) then "compute"
    elif ($NE | split(" ") | index(rtype)) then "network"
    elif ($SE | split(" ") | index(rtype)) then "security"
    else "other" end;

def has_prevent_destroy:
    [.[] | .lifecycle? // [] | .[]? | .prevent_destroy? // false] | any;

# Internet-facing detection
def is_lb_public:
    [.[] | select(.internal == false or .scheme == "internet-facing")] | length > 0;

# Group files by directory
[.[] | select(.valid) | {dir: (.path | split("/")[:-1] | join("/")), path, hcl}]
| group_by(.dir)
| map(
    (.[0].dir | if . == "" then "." else . end) as $module_path |

    # Flatten all resources across files in this module
    [.[] | .hcl.resource? // {} | to_entries[] |
        .key as $rtype | .value | to_entries[] |
        {
            type: $rtype,
            name: .key,
            configs: .value,
            category: categorize($rtype)
        }
    ] as $all_resources |

    # Check internet accessibility
    ([$all_resources[] | select(
        (.type == "aws_lb" and (.configs | is_lb_public)) or
        (.type == "aws_elb" and ([$all_resources[] | select(.type == "aws_elb")] | length > 0)) or
        (.type | IN("aws_api_gateway_rest_api", "aws_apigatewayv2_api", "aws_cloudfront_distribution"))
    )] | length > 0) as $internet_accessible |

    # Check WAF presence (need both acl and association)
    ([$all_resources[] | select(.type == "aws_wafv2_web_acl")] | length > 0) as $has_waf_acl |
    ([$all_resources[] | select(.type == "aws_wafv2_web_acl_association")] | length > 0) as $has_waf_assoc |

    {
        path: $module_path,
        resources: [$all_resources[] | {
            type, name, category,
            has_prevent_destroy: (.configs | has_prevent_destroy)
        } + (
            if (.type | IN("aws_lb", "aws_elb")) and (.configs | is_lb_public) then
                {internet_facing: true}
            elif .type | IN("aws_api_gateway_rest_api", "aws_apigatewayv2_api", "aws_cloudfront_distribution") then
                {internet_facing: true}
            else {} end
        )],
        analysis: {
            internet_accessible: $internet_accessible,
            has_waf: ($has_waf_acl and $has_waf_assoc)
        }
    }
)' | lunar collect -j ".iac.modules" -

# --- Write source metadata ---
TOOL_VERSION=$(cat /usr/local/bin/hcl2json.version 2>/dev/null || echo "unknown")
jq -n --arg version "$TOOL_VERSION" '{tool: "hcl2json", version: $version}' \
    | lunar collect -j ".iac.source" -
