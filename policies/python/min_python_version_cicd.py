from lunar_policy import Check, variable_or_default


def check_min_python_version_cicd(min_version=None, node=None):
    """Check that Python version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_python_version_cicd", "3.9")

    c = Check(
        "min-python-version-cicd",
        "Ensures CI/CD Python version meets minimum",
        node=node,
    )
    with c:
        python = c.get_node(".lang.python")
        if not python.exists():
            c.skip("Not a Python project")

        cmds_node = python.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Python commands recorded")

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
                violations.append(f"'{cmd_name}' has no Python version recorded")
                continue
            try:
                actual = parse_version(version)
                if actual[:len(minimum)] < minimum:
                    violations.append(f"'{cmd_name}' used Python {version}")
            except (ValueError, TypeError):
                violations.append(
                    f"'{cmd_name}' has unparseable version '{version}'"
                )

        if violations:
            c.fail(
                f"CI/CD Python version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_python_version_cicd()
