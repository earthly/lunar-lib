from lunar_policy import Check


def check_typescript_configured(node=None):
    """Check that TypeScript is configured in a Node.js project."""
    c = Check("typescript-configured", "Ensures TypeScript is configured", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        tsconfig = nodejs.get_node(".native.tsconfig.exists")
        if not tsconfig.exists():
            c.skip("TypeScript detection data not available")

        c.assert_true(
            tsconfig.get_value(),
            "TypeScript is not configured. Add a tsconfig.json to enable type checking."
        )
    return c


if __name__ == "__main__":
    check_typescript_configured()
