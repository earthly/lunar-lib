from lunar_policy import Check, variable_or_default


def check_min_sbt_version(min_version=None, node=None):
    """Check that sbt version meets minimum."""
    if min_version is None:
        min_version = variable_or_default("min_sbt_version", "1.9")

    c = Check("min-sbt-version", "Ensures sbt version meets minimum", node=node)
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        sbt_exists_node = scala.get_node(".build_sbt_exists")
        uses_sbt = sbt_exists_node.get_value() if sbt_exists_node.exists() else False
        if not uses_sbt:
            c.skip("Project does not use sbt")

        version_node = scala.get_node(".sbt_version")
        if not version_node.exists():
            c.skip("sbt version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("sbt version not detected")

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
                f"sbt version {actual_version} is below minimum {min_version}. "
                f"Bump project/build.properties to sbt.version={min_version} or higher.",
            )
        except (ValueError, TypeError):
            c.fail(f"Could not parse sbt version: {actual_version}")
    return c


if __name__ == "__main__":
    check_min_sbt_version()
