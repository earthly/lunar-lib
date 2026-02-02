from lunar_policy import Check


def check_tests_recursive(node=None):
    """Check that tests run recursively (./...)."""
    c = Check("tests-recursive", "Ensures tests run recursively", node=node)
    with c:
        # Skip if not a Go project
        if not c.get_node(".lang.go").exists():
            c.skip("Not a Go project")

        # Skip if test scope data not available (tests may not have run in CI)
        if not c.get_node(".lang.go.tests.scope").exists():
            c.skip("Test scope data not available - tests may not have run in CI")

        scope = c.get_value(".lang.go.tests.scope")

        c.assert_true(
            scope == "recursive",
            f"Tests run with scope '{scope}' instead of 'recursive'. "
            f"Use 'go test ./...' to run all tests in all packages."
        )
    return c


if __name__ == "__main__":
    check_tests_recursive()
