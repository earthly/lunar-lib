from lunar_policy import Check, variable_or_default


def parse_version(v):
    """Parse version string like '1.75.0' into tuple for comparison."""
    parts = str(v).split(".")
    return tuple(int(p) for p in parts)


def check_min_rust_version_cicd(min_version=None, node=None):
    """Check that Rust toolchain version in CI meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_rust_version_cicd", "1.75.0")

    c = Check("min-rust-version-cicd", "Ensures Rust CI/CD version meets minimum", node=node)
    with c:
        rust = c.get_node(".lang.rust")
        if not rust.exists():
            c.skip("Not a Rust project")

        cmds = rust.get_node(".cicd.cmds")
        if not cmds.exists():
            c.skip("No Rust CI/CD commands detected")

        try:
            minimum = parse_version(min_version)
        except (ValueError, TypeError):
            c.fail(f"Could not parse minimum version: {min_version}")

        for cmd in cmds:
            version_node = cmd.get_node(".version")
            if not version_node.exists():
                continue
            version = version_node.get_value()
            if not version:
                continue
            try:
                actual = parse_version(version)
                if actual < minimum:
                    cmd_str = cmd.get_node(".cmd").get_value() if cmd.get_node(".cmd").exists() else "unknown"
                    c.fail(
                        f"Rust version {version} in CI ('{cmd_str}') "
                        f"is below minimum {min_version}."
                    )
            except (ValueError, TypeError):
                continue
    return c


if __name__ == "__main__":
    check_min_rust_version_cicd()
