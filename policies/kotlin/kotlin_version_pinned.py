from lunar_policy import Check


def check_kotlin_version_pinned(node=None):
    """Check that the Kotlin compiler version is declared."""
    c = Check(
        "kotlin-version-pinned",
        "Ensures the Kotlin version is declared via the Gradle plugin, pom.xml, or version catalog",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")
        project_exists_node = kotlin.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Kotlin project detected in this component")

        version_node = kotlin.get_node(".version")
        version = version_node.get_value() if version_node.exists() else ""

        c.assert_true(
            bool(version) and bool(str(version).strip()),
            "Kotlin compiler version not declared. Add the Kotlin Gradle plugin "
            "with a version (e.g. `kotlin(\"jvm\") version \"1.9.22\"`), set "
            "<kotlin.version> in pom.xml, or pin it in gradle/libs.versions.toml.",
        )
    return c


if __name__ == "__main__":
    check_kotlin_version_pinned()
