"""Check that the Go version used in CI/CD meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from min_go_version import GO
from version_minimum import parse_minimum, report_ci_versions


def check_min_go_version_cicd(min_version=None, node=None):
    """Check that Go version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_go_version_cicd", "1.21")

    c = Check("min-go-version-cicd", "Ensures CI/CD Go version meets minimum", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        cmds_node = go.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Go commands recorded")

        try:
            minimum = parse_minimum(min_version, GO)
        except ValueError as e:
            c.fail(f"min_go_version_cicd {e}")
            return c
        report_ci_versions(c, cmds_node.get_value(), minimum)
    return c


if __name__ == "__main__":
    check_min_go_version_cicd()
