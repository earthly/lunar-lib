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


def check_min_gradle_version(min_version=None, node=None):
    """Check that Gradle version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_gradle_version", "8.0.0")

    c = Check("min-gradle-version", "Ensures CI/CD Gradle version meets minimum", node=node)
    with c:
        java = c.get_node(".lang.java")
        if not java.exists():
            c.skip("Not a Java project")

        cmds_node = java.get_node(".native.gradle.cicd.cmds")
        if not cmds_node.exists():
            c.skip("No Gradle CI/CD commands recorded")

        cmds = cmds_node.get_value()

        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                continue  # Skip entries without version
            try:
                if not _compare_versions(version, min_version):
                    violations.append(f"'{cmd_name}' used Gradle {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD Gradle version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_gradle_version()
