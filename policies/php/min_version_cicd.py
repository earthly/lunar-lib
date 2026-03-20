from lunar_policy import Check, variable_or_default


def check_min_version_cicd(min_version=None, node=None):
    """Check that PHP runtime version in CI meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_version_cicd", "8.1")

    c = Check("min-version-cicd", "Ensures CI PHP runtime version meets minimum", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")
        if not php.get_node(".project_exists").exists() and not php.get_node(".cicd").exists():
            c.skip("No PHP project detected in this component")

        cmds_node = php.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No PHP CI/CD commands recorded")

        cmds = cmds_node.get_value()

        # Parse versions for comparison (e.g., "8.2.15" -> (8, 2, 15))
        def parse_version(v):
            parts = str(v).split(".")
            return tuple(int(p) for p in parts)

        try:
            minimum = parse_version(min_version)
        except (ValueError, TypeError):
            c.fail(f"Invalid minimum version format: {min_version}")
            return c

        # Check all CI/CD commands for PHP version
        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                violations.append(f"'{cmd_name}' has no PHP version recorded")
                continue
            try:
                actual = parse_version(version)
                if actual[:len(minimum)] < minimum:
                    violations.append(f"'{cmd_name}' used PHP {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"PHP CI runtime version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_version_cicd()
