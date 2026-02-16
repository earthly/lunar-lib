from lunar_policy import Check, variable_or_default


def check_min_python_version(min_version=None, node=None):
    """Check that Python version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_python_version", "3.9")

    c = Check("min-python-version", "Ensures Python version meets minimum", node=node)
    with c:
        python = c.get_node(".lang.python")
        if not python.exists():
            c.skip("Not a Python project")

        version_node = python.get_node(".version")
        if not version_node.exists():
            c.skip("Python version not detected")

        actual_version = version_node.get_value()

        def parse_version(v):
            parts = str(v).split(".")
            return tuple(int(p) for p in parts)

        try:
            actual = parse_version(actual_version)
            minimum = parse_version(min_version)

            c.assert_true(
                actual[:len(minimum)] >= minimum,
                f"Python version {actual_version} is below minimum {min_version}. "
                f"Update to Python {min_version} or higher."
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse Python version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_python_version()
