from lunar_policy import Check

with Check("ran", "Codecov should run in CI") as c:
    c.assert_true(c.get_value(".testing.codecov.detected"), "Codecov not detected in CI")
