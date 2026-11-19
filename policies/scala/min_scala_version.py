"""Check that the Scala compiler version meets the minimum for its release line."""
from lunar_policy import Check, variable_or_default

from version_minimum import Runtime, check_build_version, parse_minimum

# A Scala release line is major.minor: 2.12, 2.13 and 3.3 are all maintained.
SCALA = Runtime("Scala", line_length=2, forms="2.13, 2.13.16 or 3.3.6")


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
        project_exists_node = scala.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Scala project detected in this component")

        version_node = scala.get_node(".version")
        if not version_node.exists():
            c.skip("Scala version not detected")

        actual_version = version_node.get_value()
        if not actual_version or not str(actual_version).strip():
            c.skip("Scala version not detected")

        try:
            minimum = parse_minimum(min_version, SCALA)
        except ValueError as e:
            c.fail(f"min_scala_version {e}")
            return c
        check_build_version(c, actual_version, minimum, " Update scalaVersion to {floor} or higher.")
    return c


if __name__ == "__main__":
    check_min_scala_version()
