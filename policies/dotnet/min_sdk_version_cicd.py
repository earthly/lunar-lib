from lunar_policy import Check, variable_or_default


def _parse_version(v):
    """Parse dotted version string into a tuple of ints."""
    parts = str(v).split(".")
    return tuple(int(p) for p in parts)


def _compare_versions(actual_str, min_str):
    """Compare versions with zero-padding for unequal lengths.

    Returns True if actual >= minimum.
    """
    actual = _parse_version(actual_str)
    minimum = _parse_version(min_str)
    max_len = max(len(actual), len(minimum))
    actual_padded = actual + (0,) * (max_len - len(actual))
    min_padded = minimum + (0,) * (max_len - len(minimum))
    return actual_padded >= min_padded


def check_min_sdk_version_cicd(min_version=None, node=None):
    """Check that .NET SDK version in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_sdk_version_cicd", "8.0")

    c = Check(
        "min-sdk-version-cicd",
        "Ensures CI/CD .NET SDK version meets minimum",
        node=node,
    )
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        cmds_node = dotnet.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD dotnet commands recorded")

        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No CI/CD dotnet commands recorded")

        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                continue
            try:
                if not _compare_versions(version, min_version):
                    violations.append(f"'{cmd_name}' used SDK {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD .NET SDK version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_sdk_version_cicd()
