from lunar_policy import Check


def check_gemfile_exists(node=None):
    """Check that a Gemfile exists in a Ruby project."""
    c = Check("gemfile-exists", "Ensures Gemfile exists for dependency management", node=node)
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")
        project_exists_node = ruby.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Ruby project detected in this component")

        gemfile = ruby.get_node(".gemfile_exists")
        if not gemfile.exists():
            c.skip("Ruby project data not available - ensure ruby collector has run")

        c.assert_true(
            gemfile.get_value(),
            "Gemfile not found. Initialize with 'bundle init' or create one manually."
        )
    return c


if __name__ == "__main__":
    check_gemfile_exists()
