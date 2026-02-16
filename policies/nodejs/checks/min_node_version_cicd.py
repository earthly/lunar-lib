from lunar_policy import Check, variable_or_default


def check_min_node_version_cicd(min_version=None, node=None):
    """Check that Node.js version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_node_version_cicd", "18")

    c = Check("min-node-version-cicd", "Ensures CI/CD Node.js version meets minimum", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        cmds_node = nodejs.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Node.js commands recorded")

        cmds = cmds_node.get_value()

        def parse_major(v):
            """Extract major version number from a version string."""
            return int(str(v).split(".")[0])

        try:
            min_major = parse_major(min_version)
        except (ValueError, TypeError):
            c.fail(f"Invalid minimum version format: {min_version}")
            return c

        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                violations.append(f"'{cmd_name}' has no Node.js version recorded")
                continue
            try:
                actual_major = parse_major(version)
                if actual_major < min_major:
                    violations.append(f"'{cmd_name}' used Node.js {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD Node.js version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_node_version_cicd()
