from lunar_policy import Check

with Check("executed", "Ensures tests were executed in CI") as c:
    c.assert_exists(
        ".testing",
        "No test execution data found. Ensure tests are configured to run in CI."
    )
