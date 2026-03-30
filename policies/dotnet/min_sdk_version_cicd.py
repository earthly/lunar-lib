import re
from lunar_policy import Check, variable_or_default


def _parse_dotnet_version(version_str):
    """Extract .NET SDK version components from version string.

    Handles: "8.0.100", "7.0.0", "6.0.400"
    Returns tuple of (major, minor, patch) or None if invalid.
    """
    s = str(version_str).strip()
    # Match pattern like 8.0.100 or 8.0
    m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", s)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3)) if m.group(3) else 0
        return (major, minor, patch)
    return None


def _compare_dotnet_versions(actual_str, min_str):
    """Compare .NET SDK versions. Returns True if actual >= minimum."""
    actual = _parse_dotnet_version(actual_str)
    minimum = _parse_dotnet_version(min_str)

    if actual is None or minimum is None:
        return False

    return actual >= minimum


def check_min_sdk_version_cicd(min_version=None, node=None):
    """Check that .NET SDK version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_sdk_version_cicd", "8.0")

    c = Check("min-sdk-version-cicd", "Ensures CI/CD .NET SDK version meets minimum", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        cmds_node = dotnet.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD commands recorded")

        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No CI/CD commands recorded")

        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                continue
            try:
                if not _compare_dotnet_versions(version, min_version):
                    violations.append(f"'{cmd_name}' used .NET SDK {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD .NET SDK version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
                + f"\nUpdate your CI/CD pipeline to use .NET SDK {min_version} or higher."
            )

    return c


if __name__ == "__main__":
    check_min_sdk_version_cicd()