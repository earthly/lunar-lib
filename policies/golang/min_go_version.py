from lunar_policy import Check, variable_or_default


def check_min_go_version(min_version=None, node=None):
    """Check that Go version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_go_version", "1.21")

    c = Check("min-go-version", "Ensures Go version meets minimum", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        version_node = go.get_node(".version")
        if not version_node.exists():
            c.skip("Go version not detected")

        actual_version = version_node.get_value()

        # Parse versions for comparison (e.g., "1.21" -> (1, 21))
        def parse_version(v):
            parts = str(v).split(".")
            return tuple(int(p) for p in parts)

        try:
            actual = parse_version(actual_version)
            minimum = parse_version(min_version)

            # Compare only as many components as minimum specifies
            c.assert_true(
                actual[:len(minimum)] >= minimum,
                f"Go version {actual_version} is below minimum {min_version}. "
                f"Update go.mod to require Go {min_version} or higher."
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse Go version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_go_version()
