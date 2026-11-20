"""Check that the PHP runtime used in CI meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from min_version import PHP
from version_minimum import parse_minimum, report_ci_versions


def check_min_version_cicd(min_version=None, node=None):
    """Check that PHP runtime version in CI meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_version_cicd", "8.1")

    c = Check("min-version-cicd", "Ensures CI PHP runtime version meets minimum", node=node)
    with c:
        php = c.get_node(".lang.php")
        if not php.exists():
            c.skip("Not a PHP project")

        cmds_node = php.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No PHP CI/CD commands recorded")

        try:
            minimum = parse_minimum(min_version, PHP)
        except ValueError as e:
            c.fail(f"min_version_cicd {e}")
            return c
        report_ci_versions(c, cmds_node.get_value(), minimum)
    return c


if __name__ == "__main__":
    check_min_version_cicd()
