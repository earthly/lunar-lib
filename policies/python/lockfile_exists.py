from lunar_policy import Check


def check_lockfile_exists(node=None):
    """Check that a Python dependency lockfile exists."""
    c = Check("lockfile-exists", "Ensures a dependency lockfile exists", node=node)
    with c:
        python = c.get_node(".lang.python")
        if not python.exists():
            c.skip("Not a Python project")

        native = python.get_node(".native")
        if not native.exists():
            c.skip("Python project data not available - ensure python collector has run")

        # Check for poetry.lock (presence = exists)
        if native.get_node(".poetry_lock").exists():
            return c

        # Check for Pipfile.lock (presence = exists)
        if native.get_node(".pipfile_lock").exists():
            return c

        # For requirements.txt projects, check if dependencies have pinned versions
        if native.get_node(".requirements_txt").exists():
            deps_node = python.get_node(".dependencies.direct")
            if not deps_node.exists():
                c.skip("Dependency data not available - ensure python dependencies collector has run")
            deps = deps_node.get_value()
            if deps and all(d.get("version") for d in deps):
                return c

        c.fail(
            "No dependency lockfile found. Use one of:\n"
            "  - poetry.lock (run 'poetry lock')\n"
            "  - Pipfile.lock (run 'pipenv lock')\n"
            "  - Pin all versions in requirements.txt (e.g., 'flask==3.0.0')"
        )
    return c


if __name__ == "__main__":
    check_lockfile_exists()
