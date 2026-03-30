from lunar_policy import Check


def check_dependencies_locked(node=None):
    """Check that packages.lock.json exists for dependency locking."""
    c = Check("dependencies-locked", "Ensures dependencies are locked", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        lock_node = dotnet.get_node(".packages_lock_exists")
        if not lock_node.exists():
            c.skip("Lock file data not available")

        c.assert_true(
            lock_node.get_value(),
            "No packages.lock.json found. Enable dependency locking by adding "
            "<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile> "
            "to your project files, then run 'dotnet restore'."
        )
    return c


if __name__ == "__main__":
    check_dependencies_locked()
