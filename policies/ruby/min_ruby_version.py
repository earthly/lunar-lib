from lunar_policy import Check, variable_or_default


def check_min_ruby_version(min_version=None, node=None):
    """Check that Ruby version meets minimum requirement."""
    if min_version is None:
        min_version = variable_or_default("min_ruby_version", "3.0")

    c = Check("min-ruby-version", "Ensures Ruby version meets minimum", node=node)
    with c:
        ruby = c.get_node(".lang.ruby")
        if not ruby.exists():
            c.skip("Not a Ruby project")

        version_node = ruby.get_node(".version")
        if not version_node.exists():
            c.skip("Ruby version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Ruby version not detected")

        def parse_version(v):
            parts = str(v).strip().split(".")
            return tuple(int(p) for p in parts)

        try:
            actual = parse_version(actual_version)
            minimum = parse_version(min_version)
            cmp_len = max(len(actual), len(minimum))
            actual_padded = actual + (0,) * (cmp_len - len(actual))
            minimum_padded = minimum + (0,) * (cmp_len - len(minimum))

            c.assert_true(
                actual_padded >= minimum_padded,
                f"Ruby version {actual_version} is below minimum {min_version}. "
                f"Update to Ruby {min_version} or higher.",
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse Ruby version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_ruby_version()
