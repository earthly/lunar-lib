from lunar_policy import Check

with Check("ran", "Codecov should run in CI") as c:
    c.assert_exists(".testing.coverage", "Codecov not detected in CI")
