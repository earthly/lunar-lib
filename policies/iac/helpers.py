"""Shared analysis functions for IaC policies.

Reads normalized data from .iac.modules[] — no access to .iac.native.
"""


def get_modules(check):
    """Get the .iac.modules node, skip if not present."""
    modules = check.get_node(".iac.modules")
    if not modules.exists():
        check.skip("No IaC modules found")
    return modules


def get_resources_by_category(module_node, category):
    """Get resources of a given category from a module."""
    resources = module_node.get_node(".resources")
    if not resources.exists():
        return []
    return [r for r in resources if r.get_value_or_default(".category", "") == category]


def get_unprotected(module_node, category):
    """Get resources of a category that lack prevent_destroy."""
    resources = get_resources_by_category(module_node, category)
    unprotected = []
    for r in resources:
        if not r.get_value_or_default(".has_prevent_destroy", False):
            rtype = r.get_value_or_default(".type", "unknown")
            name = r.get_value_or_default(".name", "unknown")
            unprotected.append(f"{rtype}.{name}")
    return unprotected
