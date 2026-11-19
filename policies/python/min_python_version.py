"""Check that the Python version meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# A Python release line is major.minor: 3.12, 3.13.
PYTHON = Runtime("Python", line_length=2, forms="3.12, 3.12.8 or 3.13.0rc1")


def check_min_python_version(min_version=None, node=None):
    """Check that Python version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_python_version", "3.9")

    c = Check("min-python-version", "Ensures Python version meets minimum", node=node)
    with c:
        python = c.get_node(".lang.python")
        if not python.exists():
            c.skip("Not a Python project")
        project_exists_node = python.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Python project detected in this component")

        version_node = python.get_node(".version")
        if not version_node.exists():
            c.skip("Python version not detected")

        try:
            minimum = parse_minimum(min_version, PYTHON)
        except ValueError as e:
            c.fail(f"min_python_version {e}")
            return c
        check_build_version(c, version_node.get_value(), minimum, " Update to Python {floor} or higher.")
    return c


if __name__ == "__main__":
    check_min_python_version()
