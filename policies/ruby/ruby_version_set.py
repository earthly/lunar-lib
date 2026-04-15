from lunar_policy import Check


def check_ruby_version_set(node=None):
    """Check that the Ruby version is explicitly specified."""
    c = Check(
        "ruby-version-set",
        "Ensures Ruby version is pinned via .ruby-version or Gemfile",
        node=node,
    )
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        # Check .ruby-version file
        version_file = ruby.get_node(".ruby_version_file_exists")
        has_version_file = (
            version_file.exists() and version_file.get_value()
        )

        # Check parsed version string (from .ruby-version, Gemfile, or Gemfile.lock)
        version_node = ruby.get_node(".version")
        has_version = (
            version_node.exists()
            and version_node.get_value()
            and str(version_node.get_value()).strip() != ""
        )

        if has_version_file or has_version:
            return c  # pass — version is specified

        c.fail(
            "Ruby version not specified. Create a .ruby-version file "
            "(e.g., 'echo \"3.2.2\" > .ruby-version') or add a ruby directive "
            "to your Gemfile (e.g., ruby \"3.2.2\")."
        )
    return c


if __name__ == "__main__":
    check_ruby_version_set()
