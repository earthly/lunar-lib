from lunar_policy import Check, variable_or_default


def check_min_maven_version(min_version=None, node=None):
    """Check that Maven version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_maven_version", "3.9.0")

    c = Check("min-maven-version", "Ensures CI/CD Maven version meets minimum", node=node)
    with c:
        java = c.get_node(".lang.java")
        if not java.exists():
            c.skip("Not a Java project")

        cmds_node = java.get_node(".native.maven.cicd.cmds")
        if not cmds_node.exists():
            c.skip("No Maven CI/CD commands recorded")

        cmds = cmds_node.get_value()

        def parse_version(v):
            parts = str(v).split(".")
            return tuple(int(p) for p in parts)

        try:
            minimum = parse_version(min_version)
        except (ValueError, TypeError):
            c.fail(f"Invalid minimum version format: {min_version}")
            return c

        violations = []
        for cmd_info in cmds:
            cmd_name = cmd_info.get("cmd", "unknown")
            version = cmd_info.get("version")
            if not version:
                violations.append(f"'{cmd_name}' has no Maven version recorded")
                continue
            try:
                actual = parse_version(version)
                if actual[:len(minimum)] < minimum:
                    violations.append(f"'{cmd_name}' used Maven {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD Maven version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_maven_version()
