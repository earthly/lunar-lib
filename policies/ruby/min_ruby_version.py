"""Check that the Ruby version meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# A Ruby release line is major.minor: 3.3, 3.4.
RUBY = Runtime("Ruby", line_length=2, forms="3.3, 3.3.6 or 3.4.0preview2")


def check_min_ruby_version(min_version=None, node=None):
    """Check that Ruby version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_ruby_version", "3.0")

    c = Check("min-ruby-version", "Ensures Ruby version meets minimum", node=node)
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")
        project_exists_node = ruby.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Ruby project detected in this component")

        version_node = ruby.get_node(".version")
        if not version_node.exists():
            c.skip("Ruby version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Ruby version not detected")

        try:
            minimum = parse_minimum(min_version, RUBY)
        except ValueError as e:
            c.fail(f"min_ruby_version {e}")
            return c
        check_build_version(c, actual_version, minimum, " Update to Ruby {floor} or higher.")
    return c


if __name__ == "__main__":
    check_min_ruby_version()
