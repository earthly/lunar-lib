from lunar_policy import Check


def check_build_tool_manifest_exists(node=None):
    """Check that the project has a recognised Kotlin build manifest."""
    c = Check(
        "build-tool-manifest-exists",
        "Ensures build.gradle.kts, build.gradle, or pom.xml (with kotlin-maven-plugin) is present",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")

        kts_node = kotlin.get_node(".build_gradle_kts_exists")
        gradle_node = kotlin.get_node(".build_gradle_exists")
        pom_node = kotlin.get_node(".pom_xml_exists")

        has_kts = kts_node.get_value() if kts_node.exists() else False
        has_gradle = gradle_node.get_value() if gradle_node.exists() else False
        has_pom = pom_node.get_value() if pom_node.exists() else False

        c.assert_true(
            has_kts or has_gradle or has_pom,
            "No Kotlin build manifest found. Add build.gradle.kts (Gradle "
            "Kotlin DSL), build.gradle (Groovy DSL), or pom.xml with the "
            "kotlin-maven-plugin (Maven).",
        )
    return c


if __name__ == "__main__":
    check_build_tool_manifest_exists()
