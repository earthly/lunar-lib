from lunar_policy import Check


def check_tests_all_modules(node=None):
    """Check that tests run across all modules (not just a subset)."""
    c = Check("tests-all-modules", "Ensures tests run all modules", node=node)
    with c:
        java = c.get_node(".lang.java")
        if not java.exists():
            c.skip("Not a Java project")

        scope_node = java.get_node(".tests.scope")
        if not scope_node.exists():
            c.skip("Test scope data not available - tests may not have run in CI")

        scope = scope_node.get_value()

        c.assert_true(
            scope == "all",
            f"Tests run with scope '{scope}' instead of 'all'. "
            "Run tests across all modules to ensure full coverage. "
            "Remove -pl/--projects flags from Maven or --tests filters from Gradle."
        )
    return c


if __name__ == "__main__":
    check_tests_all_modules()
