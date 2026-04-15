from lunar_policy import Check


def check_lockfile_exists(node=None):
    """Check that Gemfile.lock exists for reproducible dependency resolution."""
    c = Check("lockfile-exists", "Ensures Gemfile.lock exists for reproducible builds", node=node)
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        gemfile = ruby.get_node(".gemfile_exists")
        if not gemfile.exists() or not gemfile.get_value():
            c.skip("No Gemfile present - lockfile check not applicable")

        lockfile = ruby.get_node(".gemfile_lock_exists")
        if not lockfile.exists():
            c.skip("Lockfile data not available - ensure ruby collector has run")

        c.assert_true(
            lockfile.get_value(),
            "Gemfile.lock not found. Run 'bundle install' and commit the lockfile "
            "for reproducible builds."
        )
    return c


if __name__ == "__main__":
    check_lockfile_exists()
