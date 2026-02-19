from lunar_policy import Check


def check_lockfile_exists(node=None):
    """Check that a package lockfile exists in a Node.js project."""
    c = Check("lockfile-exists", "Ensures a package lockfile exists", node=node)
    with c:
        nodejs = c.get_node(".lang.nodejs")
        if not nodejs.exists():
            c.skip("Not a Node.js project")

        package_lock = nodejs.get_value_or_default(".package_lock_exists", False)
        yarn_lock = nodejs.get_value_or_default(".yarn_lock_exists", False)
        pnpm_lock = nodejs.get_value_or_default(".pnpm_lock_exists", False)

        c.assert_true(
            package_lock or yarn_lock or pnpm_lock,
            "No lockfile found. Run 'npm install', 'yarn install', or 'pnpm install' "
            "to generate a lockfile and commit it to version control."
        )
    return c


if __name__ == "__main__":
    check_lockfile_exists()
