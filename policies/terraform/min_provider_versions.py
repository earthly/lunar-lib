"""Enforce minimum version requirements for Terraform providers."""

import json
import re

from lunar_policy import Check, variable_or_default
from helpers import get_providers


def _parse_version(v):
    """Parse a version string into a comparable tuple, stripping constraint operators."""
    v = re.sub(r'^[~>=<!\s]+', '', v.strip())
    parts = re.split(r'[.\-+]', v)
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(p)
    return tuple(result)


def main(node=None):
    c = Check("min-provider-versions", "Providers meet minimum version requirements", node=node)
    with c:
        min_versions_str = variable_or_default("min_provider_versions", "{}")
        try:
            min_versions = json.loads(min_versions_str)
        except json.JSONDecodeError:
            raise ValueError(
                f"Policy misconfiguration: 'min_provider_versions' must be valid JSON, "
                f"got '{min_versions_str}'"
            )

        if not min_versions:
            c.skip("No minimum provider versions configured")

        native = c.get_node(".iac.native.terraform.files")
        if not native.exists():
            c.skip("No Terraform data found")

        providers = get_providers(native)
        if not providers:
            c.skip("No providers found in required_providers")

        provider_map = {p["name"]: p["version_constraint"] for p in providers}

        for provider_name, min_version in min_versions.items():
            constraint = provider_map.get(provider_name)
            if constraint is None:
                c.fail(f"Provider '{provider_name}' not found in required_providers")
                continue
            # Extract version number from constraint (e.g., "~> 5.0" -> "5.0")
            actual = _parse_version(constraint)
            required = _parse_version(min_version)
            if actual < required:
                c.fail(
                    f"Provider '{provider_name}' version constraint '{constraint}' "
                    f"is below minimum required '{min_version}'"
                )
    return c


if __name__ == "__main__":
    main()
