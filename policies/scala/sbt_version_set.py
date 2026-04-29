from lunar_policy import Check


def check_sbt_version_set(node=None):
    """Check that project/build.properties pins the sbt version when sbt is in use."""
    c = Check(
        "sbt-version-set",
        "Ensures project/build.properties pins sbt.version",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        # Skip Mill-only / Maven-only projects — sbt.version only applies when
        # the project actually uses sbt.
        sbt_exists_node = scala.get_node(".build_sbt_exists")
        uses_sbt = sbt_exists_node.get_value() if sbt_exists_node.exists() else False
        if not uses_sbt:
            c.skip("Project does not use sbt")

        sbt_version_node = scala.get_node(".sbt_version")
        sbt_version = sbt_version_node.get_value() if sbt_version_node.exists() else ""

        c.assert_true(
            bool(sbt_version) and bool(str(sbt_version).strip()),
            "sbt version not pinned. Add `sbt.version=X.Y.Z` to "
            "project/build.properties for reproducible builds.",
        )
    return c


if __name__ == "__main__":
    check_sbt_version_set()
