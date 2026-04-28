from lunar_policy import Check


def check_build_tool_manifest_exists(node=None):
    """Check that the project has a recognised Scala build manifest."""
    c = Check(
        "build-tool-manifest-exists",
        "Ensures build.sbt, build.sc, or pom.xml (with scala-maven-plugin) is present",
        node=node,
    )
    with c:
        scala = c.get_node(".lang.scala")
        if not scala.exists():
            c.skip("Not a Scala project")

        sbt_node = scala.get_node(".build_sbt_exists")
        sc_node = scala.get_node(".build_sc_exists")
        pom_node = scala.get_node(".pom_xml_exists")

        has_sbt = sbt_node.get_value() if sbt_node.exists() else False
        has_sc = sc_node.get_value() if sc_node.exists() else False
        has_pom = pom_node.get_value() if pom_node.exists() else False

        c.assert_true(
            has_sbt or has_sc or has_pom,
            "No Scala build manifest found. Add build.sbt (sbt), "
            "build.sc (Mill), or pom.xml with the scala-maven-plugin (Maven).",
        )
    return c


if __name__ == "__main__":
    check_build_tool_manifest_exists()
