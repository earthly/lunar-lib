from lunar_policy import Check

with Check("passing", "Ensures all tests pass") as c:
    # First check if we have test execution data at all
    if not c.exists(".testing"):
        c.skip("No test execution data found")

    # Check if pass/fail data is available
    if not c.exists(".testing.all_passing"):
        c.skip(
            "Test pass/fail data not available. "
            "This requires a collector that reports detailed test results."
        )

    # Assert tests are passing
    c.assert_true(
        c.get_value(".testing.all_passing"),
        "Tests are failing. Check CI logs for test failure details."
    )
