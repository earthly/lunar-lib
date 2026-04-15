from lunar_policy import Check, variable_or_default


def check_min_rake_version_cicd(min_version=None, node=None):
    """Check that Rake version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_rake_version_cicd", "13.0")

    c = Check(
        "min-rake-version-cicd",
        "Ensures CI/CD Rake version meets minimum",
        node=node,
    )
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        cmds_node = ruby.get_node(".rake.cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Rake commands recorded")

        cmds = cmds_node.get_value()

        def parse_version(v):
            parts = str(v).strip().split(".")
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
                continue
            try:
                actual = parse_version(version)
                cmp_len = max(len(actual), len(minimum))
                actual_padded = actual + (0,) * (cmp_len - len(actual))
                minimum_padded = minimum + (0,) * (cmp_len - len(minimum))
                if actual_padded < minimum_padded:
                    violations.append(f"'{cmd_name}' used Rake {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD Rake version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_rake_version_cicd()
