from lunar_policy import Check


def check_scala_version_pinned(node=None):
    """Check that the Scala compiler version is declared."""
    c = Check(
        "scala-version-pinned",
        "Ensures scalaVersion is declared in build.sbt, build.sc, or pom.xml",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        version_node = scala.get_node(".version")
        version = version_node.get_value() if version_node.exists() else ""

        c.assert_true(
            bool(version) and bool(str(version).strip()),
            "Scala compiler version not declared. Add `scalaVersion := \"X.Y.Z\"` "
            "to build.sbt, `def scalaVersion = \"X.Y.Z\"` to build.sc, or "
            "<scala.version> to pom.xml.",
        )
    return c


if __name__ == "__main__":
    check_scala_version_pinned()
