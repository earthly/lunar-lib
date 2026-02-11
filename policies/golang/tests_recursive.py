from lunar_policy import Check


def check_tests_recursive(node=None):
    """Check that tests run recursively (./...)."""
    c = Check("tests-recursive", "Ensures tests run recursively", node=node)
    with c:
        go = c.get_node(".lang.go")
        if not go.exists():
            c.skip("Not a Go project")

        scope_node = go.get_node(".tests.scope")
        if not scope_node.exists():
            c.skip("Test scope data not available - tests may not have run in CI")

        scope = scope_node.get_value()

        c.assert_true(
            scope == "recursive",
            f"Tests run with scope '{scope}' instead of 'recursive'. "
            f"Use 'go test ./...' to run all tests in all packages."
        )
    return c


if __name__ == "__main__":
    check_tests_recursive()
