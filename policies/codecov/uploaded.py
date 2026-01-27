from lunar_policy import Check

with Check("uploaded", "Codecov upload should run in CI") as c:
    c.assert_exists(".testing.coverage.percentage", "Codecov upload not detected in CI")
