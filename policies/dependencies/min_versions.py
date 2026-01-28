import json
import semver
from lunar_policy import Check, variable_or_default


def check_min_versions(language, min_versions, include_indirect=False, node=None):
    """
    Check that dependencies meet minimum version requirements.
    
    Args:
        language: Programming language to check (e.g., 'go', 'java', 'python')
        min_versions: Dict mapping dependency paths to minimum versions
        include_indirect: Whether to also check indirect dependencies
        node: Optional Node for testing (if None, reads from component JSON)
    
    Returns:
        Check object with results
    """
    c = Check("min-versions", "Ensures dependencies meet minimum safe version requirements", node=node)
    with c:
        # Skip if language data doesn't exist
        lang_node = c.get_node(f".lang.{language}")
        if not lang_node.exists():
            c.skip(f"No {language} language data found")
            return c
        
        if min_versions:
            # Build list of dependency paths to check
            dep_paths = [f".lang.{language}.dependencies.direct"]
            if include_indirect:
                dep_paths.append(f".lang.{language}.dependencies.indirect")
            
            for dep_path in dep_paths:
                deps = c.get_node(dep_path)
                if deps.exists():
                    for dep in deps:
                        dep_name = dep.get_value_or_default(".path", "")
                        dep_version = dep.get_value_or_default(".version", "")
                        
                        if dep_name in min_versions and dep_version:
                            try:
                                # Strip common prefixes (v1.2.3 -> 1.2.3)
                                v = semver.VersionInfo.parse(dep_version.lstrip('v'))
                                min_v = semver.VersionInfo.parse(min_versions[dep_name].lstrip('v'))
                                
                                c.assert_greater_or_equal(
                                    v, min_v,
                                    f"'{dep_name}' version {dep_version} is below minimum safe version {min_versions[dep_name]}"
                                )
                            except ValueError:
                                # Non-semver versions (pseudo-versions, etc.) - fail with helpful message
                                c.fail(
                                    f"Cannot parse version for '{dep_name}': {dep_version} - "
                                    f"ensure versions follow semver format (e.g., '1.2.3')"
                                )
    return c


# Production entry point
if __name__ == "__main__":
    language = variable_or_default("language", "")
    min_versions_str = variable_or_default("min_versions", "{}")
    include_indirect = variable_or_default("include_indirect", "false").lower() == "true"
    
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
    
    check_min_versions(language, min_versions, include_indirect)
