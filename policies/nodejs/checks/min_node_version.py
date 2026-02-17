"""Check that Node.js version meets minimum requirement."""
from lunar_policy import Check, variable_or_default


def parse_major(v):
    """Extract major version number from a version string."""
    s = str(v).strip().lstrip("vV")
    return int(s.split(".")[0])


def check_min_node_version(min_version=None, node=None):
    """Check that Node.js version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_node_version", "18")

    c = Check("min-node-version", "Ensures Node.js version meets minimum", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        version_node = nodejs.get_node(".version")
        if not version_node.exists():
            c.skip("Node.js version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Node.js version not detected")

        try:
            min_major = parse_major(min_version)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid min_node_version input: {min_version}")

        try:
            actual_major = parse_major(actual_version)
        except (ValueError, TypeError):
            c.fail(f"Could not parse Node.js version: {actual_version}")
            return c

        c.assert_true(
            actual_major >= min_major,
            f"Node.js version {actual_version} is below minimum {min_version}. "
            f"Update to Node.js {min_version} or higher."
        )
    return c


if __name__ == "__main__":
    check_min_node_version()
