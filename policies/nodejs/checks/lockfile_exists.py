from lunar_policy import Check


def check_lockfile_exists(node=None):
    """Check that a package lockfile exists in a Node.js project."""
    c = Check("lockfile-exists", "Ensures a package lockfile exists", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        native = nodejs.get_node(".native")
        if not native.exists():
            c.skip("Node.js project data not available")

        package_lock = native.get_value_or_default(".package_lock.exists", False)
        yarn_lock = native.get_value_or_default(".yarn_lock.exists", False)
        pnpm_lock = native.get_value_or_default(".pnpm_lock.exists", False)

        c.assert_true(
            package_lock or yarn_lock or pnpm_lock,
            "No lockfile found. Run 'npm install', 'yarn install', or 'pnpm install' "
            "to generate a lockfile and commit it to version control."
        )
    return c


if __name__ == "__main__":
    check_lockfile_exists()
