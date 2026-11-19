"""Check that the Ruby version used in CI/CD meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from min_ruby_version import RUBY
from version_minimum import parse_minimum, report_ci_versions


def check_min_ruby_version_cicd(min_version=None, node=None):
    """Check that Ruby version used in CI/CD meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_ruby_version_cicd", "3.0")

    c = Check(
        "min-ruby-version-cicd",
        "Ensures CI/CD Ruby version meets minimum",
        node=node,
    )
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        cmds_node = ruby.get_node(".cicd.cmds")
        if not cmds_node.exists():
            c.skip("No CI/CD Ruby commands recorded")

        try:
            minimum = parse_minimum(min_version, RUBY)
        except ValueError as e:
            c.fail(f"min_ruby_version_cicd {e}")
            return c
        report_ci_versions(c, cmds_node.get_value(), minimum, skip_unrecorded=True)
    return c


if __name__ == "__main__":
    check_min_ruby_version_cicd()
