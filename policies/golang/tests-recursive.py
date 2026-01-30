from lunar_policy import Check

with Check("tests-recursive", "Ensures tests run recursively") as c:
    # Skip if not a Go project
    if not c.exists(".lang.go"):
        c.skip("Not a Go project")

    # Skip if test scope data not available (tests may not have run in CI)
    if not c.exists(".lang.go.tests.scope"):
        c.skip("Test scope data not available - tests may not have run in CI")

    scope = c.get_value(".lang.go.tests.scope")

    c.assert_true(
        scope == "recursive",
        f"Tests run with scope '{scope}' instead of 'recursive'. "
        f"Use 'go test ./...' to run all tests in all packages."
    )
