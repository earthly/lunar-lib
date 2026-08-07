from lunar_policy import Check


def check_build_tool_wrapper_exists(node=None):
    """Check that the Gradle wrapper is committed for Gradle projects."""
    c = Check(
        "build-tool-wrapper-exists",
        "Ensures the Gradle wrapper (gradlew) is committed for Gradle projects",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")
        project_exists_node = kotlin.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Kotlin project detected in this component")

        build_systems_node = kotlin.get_node(".build_systems")
        build_systems = build_systems_node.get_value() if build_systems_node.exists() else []

        if "gradle" not in build_systems:
            c.skip("Not a Gradle project — Gradle wrapper check does not apply")

        gradlew_node = kotlin.get_node(".gradlew_exists")
        has_gradlew = gradlew_node.get_value() if gradlew_node.exists() else False

        c.assert_true(
            has_gradlew,
            "Gradle wrapper not found. Run `gradle wrapper` and commit gradlew, "
            "gradlew.bat, and gradle/wrapper/ for reproducible builds without a "
            "pre-installed Gradle.",
        )
    return c


if __name__ == "__main__":
    check_build_tool_wrapper_exists()
