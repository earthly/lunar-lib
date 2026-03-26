from lunar_policy import Check


def check_dependencies_locked(node=None):
    """Check that packages.lock.json exists for dependency locking."""
    c = Check("dependencies-locked", "Ensures dependencies are locked", node=node)
    with c:
        dotnet = c.get_node(".lang.dotnet")
        if not dotnet.exists():
            c.skip("Not a .NET project")

        packages_lock_exists = dotnet.get_node(".packages_lock_exists")
        if not packages_lock_exists.exists():
            c.skip(".NET project data not available - ensure dotnet collector has run")

        lock_exists = packages_lock_exists.get_value()

        if not lock_exists:
            c.warn(
                "No packages.lock.json found. Dependencies are not locked.\n\n"
                "To enable package locking:\n"
                "1. Add <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile> to all project files\n"
                "2. Run 'dotnet restore' to generate packages.lock.json\n"
                "3. Commit packages.lock.json files to version control\n\n"
                "This ensures reproducible builds and better supply chain security."
            )
        else:
            c.pass_check("Dependencies are locked with packages.lock.json")

    return c


if __name__ == "__main__":
    check_dependencies_locked()