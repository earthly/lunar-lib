"""Check that the Node.js version used in CI/CD meets the minimum for its major release."""
from lunar_policy import Check, variable_or_default

from min_node_version import NODE
from version_minimum import parse_minimum, report_ci_versions


def check_min_node_version_cicd(min_version=None, node=None):
    """Check that Node.js version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_node_version_cicd", "18")

    c = Check("min-node-version-cicd", "Ensures CI/CD Node.js version meets minimum", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        cmds_node = nodejs.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Node.js commands recorded")

        try:
            minimum = parse_minimum(min_version, NODE)
        except ValueError as e:
            c.fail(f"min_node_version_cicd {e}")
            return c
        report_ci_versions(c, cmds_node.get_value(), minimum)
    return c


if __name__ == "__main__":
    check_min_node_version_cicd()
