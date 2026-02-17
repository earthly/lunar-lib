from lunar_policy import Check


def check_engines_pinned(node=None):
    """Check that engines.node is set in package.json."""
    c = Check("engines-pinned", "Ensures engines.node is set in package.json", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        engines_node = nodejs.get_node(".native.engines_node")
        if not engines_node.exists():
            c.fail(
                "engines.node is not set in package.json. "
                "Add an engines field to pin the required Node.js version, e.g.: "
                '"engines": { "node": ">=18" }'
            )
            return c

        value = engines_node.get_value()
        c.assert_true(
            value and str(value).strip(),
            "engines.node is empty in package.json. "
            "Set a version constraint, e.g.: \">=18\""
        )
    return c


if __name__ == "__main__":
    check_engines_pinned()
