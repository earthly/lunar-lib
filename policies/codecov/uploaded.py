from lunar_policy import Check

with Check("uploaded", "Codecov upload should run in CI") as c:
    c.assert_true(c.get_value(".testing.codecov.uploaded"), "Codecov upload not detected in CI")
