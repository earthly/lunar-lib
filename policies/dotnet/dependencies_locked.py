from lunar_policy import Check


def check_dependencies_locked(node=None):
    """Check that dependencies are locked with packages.lock.json."""
    c = Check("dependencies-locked", "Ensures packages.lock.json exists", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        packages_lock_node = dotnet.get_node(".packages_lock_exists")
        if not packages_lock_node.exists() or not packages_lock_node.get_value():
            c.fail(
                "No packages.lock.json found. Dependencies are not locked. "
                "Add <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile> to project files and run 'dotnet restore'."
            )

    return c


if __name__ == "__main__":
    check_dependencies_locked()