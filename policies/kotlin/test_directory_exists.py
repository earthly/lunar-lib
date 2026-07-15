from lunar_policy import Check


def check_test_directory_exists(node=None):
    """Check that the project has a Kotlin test source directory."""
    c = Check(
        "test-directory-exists",
        "Ensures src/test/kotlin (or an Android/Multiplatform variant) exists",
        node=node,
    )
    with c:
        kotlin = c.get_node(".lang.kotlin")
        if not kotlin.exists():
            c.skip("Not a Kotlin project")
        project_exists_node = kotlin.get_node(".project_exists")
        if not project_exists_node.exists() or not project_exists_node.get_value():
            c.skip("No Kotlin project detected in this component")

        test_node = kotlin.get_node(".test_directory_exists")
        has_tests = test_node.get_value() if test_node.exists() else False

        c.assert_true(
            has_tests,
            "No Kotlin test source directory found. Add src/test/kotlin/ (or the "
            "Android/Multiplatform equivalent) with JUnit, Kotest, or MockK tests.",
        )
    return c


if __name__ == "__main__":
    check_test_directory_exists()
