import json
import semver
from lunar_policy import Check, variable_or_default

with Check("dependency-versions", "Ensures dependencies meet minimum safe version requirements") as c:
    language = variable_or_default("language", "")
    min_versions_str = variable_or_default("min_versions", "{}")
    
    # Validate language input
    if not language:
        raise ValueError(
            "Policy misconfiguration: 'language' must be specified. "
            "Set this to the programming language to check (e.g., 'go', 'java', 'python')."
        )
    
    # Parse min_versions JSON
    try:
        min_versions = json.loads(min_versions_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Policy misconfiguration: 'min_versions' is not valid JSON: {e}")
    
    # Empty min_versions = no requirements = pass early
    if not min_versions:
        pass  # No minimum version requirements configured
    else:
        deps = c.get_node(f".lang.{language}.dependencies.direct")
        if deps.exists():
            for dep in deps:
                dep_path = dep.get_value_or_default(".path", "")
                dep_version = dep.get_value_or_default(".version", "")
                
                if dep_path in min_versions and dep_version:
                    try:
                        # Strip common prefixes (v1.2.3 -> 1.2.3)
                        v = semver.VersionInfo.parse(dep_version.lstrip('v'))
                        min_v = semver.VersionInfo.parse(min_versions[dep_path].lstrip('v'))
                        
                        c.assert_greater_or_equal(
                            v, min_v,
                            f"'{dep_path}' version {dep_version} is below minimum safe version {min_versions[dep_path]}"
                        )
                    except ValueError as e:
                        # Non-semver versions (pseudo-versions, etc.) - fail with helpful message
                        c.fail(
                            f"Cannot parse version for '{dep_path}': {dep_version} - "
                            f"ensure versions follow semver format (e.g., '1.2.3')"
                        )
