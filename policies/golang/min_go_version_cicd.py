from lunar_policy import Check, variable_or_default


def check_min_go_version_cicd(min_version=None, node=None):
    """Check that Go version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_go_version_cicd", "1.21")

    c = Check("min-go-version-cicd", "Ensures CI/CD Go version meets minimum", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        cmds_node = go.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Go commands recorded")

        cmds = cmds_node.get_value()

        # Parse versions for comparison (e.g., "1.21.5" -> (1, 21, 5))
        def parse_version(v):
            parts = str(v).split(".")
            return tuple(int(p) for p in parts)

        try:
            minimum = parse_version(min_version)
        except (ValueError, TypeError):
            c.fail(f"Invalid minimum version format: {min_version}")
            return c

        # Check all CI/CD commands for Go version
        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                violations.append(f"'{cmd_name}' has no Go version recorded")
                continue
            try:
                actual = parse_version(version)
                if actual[:len(minimum)] < minimum:
                    violations.append(f"'{cmd_name}' used Go {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD Go version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_go_version_cicd()
