from lunar_policy import Check, variable_or_default


def check_min_scala_version(min_version=None, node=None):
    """Check that the Scala compiler version meets the configured minimum."""
    if min_version is None:
        min_version = variable_or_default("min_scala_version", "2.12")

    c = Check(
        "min-scala-version",
        "Ensures Scala compiler version meets minimum",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        version_node = scala.get_node(".version")
        if not version_node.exists():
            c.skip("Scala version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Scala version not detected")

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
                f"Scala version {actual_version} is below minimum {min_version}. "
                f"Update scalaVersion to {min_version} or higher.",
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse Scala version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_scala_version()
