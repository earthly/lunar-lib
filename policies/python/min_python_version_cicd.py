"""Check that the Python version used in CI/CD meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from min_python_version import PYTHON
from version_minimum import parse_minimum, report_ci_versions


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

        try:
            minimum = parse_minimum(min_version, PYTHON)
        except ValueError as e:
            c.fail(f"min_python_version_cicd {e}")
            return c
        report_ci_versions(c, cmds_node.get_value(), minimum)
    return c


if __name__ == "__main__":
    check_min_python_version_cicd()
