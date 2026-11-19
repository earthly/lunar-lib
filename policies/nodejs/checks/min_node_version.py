"""Check that the Node.js version meets the minimum for its major release."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# A Node.js release line is a major: 20, 22.
NODE = Runtime("Node.js", line_length=1, forms="20, 20.15.1 or v20.15.1")


def check_min_node_version(min_version=None, node=None):
    """Check that Node.js version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_node_version", "18")

    c = Check("min-node-version", "Ensures Node.js version meets minimum", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")
        project_exists_node = nodejs.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Node.js project detected in this component")

        version_node = nodejs.get_node(".version")
        if not version_node.exists():
            c.skip("Node.js version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Node.js version not detected")

        try:
            minimum = parse_minimum(min_version, NODE)
        except ValueError as e:
            c.fail(f"min_node_version {e}")
            return c
        check_build_version(c, actual_version, minimum, " Update to Node.js {floor} or higher.")
    return c


if __name__ == "__main__":
    check_min_node_version()
