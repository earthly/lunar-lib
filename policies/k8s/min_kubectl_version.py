from lunar_policy import Check, variable_or_default


def parse_version(v):
    """Parse version string like '1.29.2' into tuple for comparison."""
    parts = str(v).lstrip("vV").split(".")
    return tuple(int(p) for p in parts)


def check_min_kubectl_version(min_version=None, node=None):
    """Check that kubectl version used in CI meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_kubectl_version", "1.28")

    c = Check("min-kubectl-version", "Ensures kubectl version in CI meets minimum", node=node)
    with c:
        cmds_node = c.get_node(".k8s.cicd.cmds")
        if not cmds_node.exists():
            c.skip("No kubectl CI/CD commands recorded")

        cmds = cmds_node.get_value()
        if not cmds:
            c.skip("No kubectl CI/CD commands recorded")

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
                violations.append(f"'{cmd_name}' has no kubectl version recorded")
                continue
            try:
                actual = parse_version(version)
                if actual[:len(minimum)] < minimum:
                    violations.append(f"'{cmd_name}' used kubectl {version}")
            except (ValueError, TypeError):
                violations.append(f"'{cmd_name}' has unparseable version '{version}'")

        if violations:
            c.fail(
                f"CI/CD kubectl version issues (minimum: {min_version}):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
    return c


if __name__ == "__main__":
    check_min_kubectl_version()
