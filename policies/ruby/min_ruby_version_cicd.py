from lunar_policy import Check, variable_or_default


def check_min_ruby_version_cicd(min_version=None, node=None):
    """Check that Ruby version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_ruby_version_cicd", "3.0")

    c = Check(
        "min-ruby-version-cicd",
        "Ensures CI/CD Ruby version meets minimum",
        node=node,
    )
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        cmds_node = ruby.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Ruby commands recorded")

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
                    violations.append(f"'{cmd_name}' used Ruby {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD Ruby version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_ruby_version_cicd()
