"""Shared analysis functions for IaC policies.

Walks .iac.native.terraform.files[].hcl to extract infrastructure properties.
"""

INTERNET_FACING_RESOURCES = {
    "aws_lb": lambda instances: any(
        cfg.get("internal") is False or cfg.get("scheme") == "internet-facing"
        for name, cfgs in instances.items() for cfg in cfgs
    ),
    "aws_elb": lambda instances: any(
        not cfg.get("internal", False)
        for name, cfgs in instances.items() for cfg in cfgs
    ),
    "aws_api_gateway_rest_api": lambda instances: len(instances) > 0,
    "aws_apigatewayv2_api": lambda instances: len(instances) > 0,
    "aws_cloudfront_distribution": lambda instances: len(instances) > 0,
}

WAF_RESOURCE_TYPES = {"aws_wafv2_web_acl", "aws_wafv2_web_acl_association"}

DEFAULT_DATASTORE_TYPES = [
    "aws_s3_bucket", "aws_db_instance", "aws_dynamodb_table",
    "aws_elasticache_cluster", "aws_elasticache_replication_group",
    "aws_ebs_volume", "aws_efs_file_system",
]

DEFAULT_STATELESS_TYPES = [
    "aws_instance", "aws_lb", "aws_autoscaling_group",
    "aws_ecs_service", "aws_lambda_function",
]


def iter_resources(native_files_node):
    """Yield (resource_type, name, config_list) from all parsed TF files."""
    if not native_files_node.exists():
        return
    for f in native_files_node:
        hcl = f.get_node(".hcl")
        if not hcl.exists():
            continue
        resources = hcl.get_node(".resource")
        if not resources.exists():
            continue
        raw = resources.get_value()
        if not isinstance(raw, dict):
            continue
        for rtype, instances in raw.items():
            if not isinstance(instances, dict):
                continue
            for name, configs in instances.items():
                if isinstance(configs, list):
                    yield rtype, name, configs


def is_internet_accessible(native_files_node):
    """Check if any resources indicate internet accessibility."""
    for rtype, name, configs in iter_resources(native_files_node):
        checker = INTERNET_FACING_RESOURCES.get(rtype)
        if checker:
            # Build a dict matching what the checker expects
            if checker({name: configs}):
                return True
    return False


def has_waf_protection(native_files_node):
    """Check if WAF resources are present and associated."""
    has_waf = False
    has_association = False
    for rtype, name, configs in iter_resources(native_files_node):
        if rtype == "aws_wafv2_web_acl":
            has_waf = True
        if rtype == "aws_wafv2_web_acl_association":
            has_association = True
    return has_waf and has_association


def _has_prevent_destroy(configs):
    """Check if a resource config list has lifecycle { prevent_destroy = true }."""
    for cfg in configs:
        lifecycle = cfg.get("lifecycle", [])
        if isinstance(lifecycle, list):
            for lc in lifecycle:
                if isinstance(lc, dict) and lc.get("prevent_destroy", False):
                    return True
        elif isinstance(lifecycle, dict):
            if lifecycle.get("prevent_destroy", False):
                return True
    return False


def check_destroy_protection(native_files_node, resource_types):
    """Check resources of given types for lifecycle { prevent_destroy }.

    Returns: (count, unprotected_names)
    """
    count = 0
    unprotected = []
    for rtype, name, configs in iter_resources(native_files_node):
        if rtype not in resource_types:
            continue
        count += 1
        if not _has_prevent_destroy(configs):
            unprotected.append(f"{rtype}.{name}")
    return count, unprotected
