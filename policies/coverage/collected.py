from lunar_policy import Check

with Check("collected", "Coverage data should be collected in CI") as c:
    c.assert_exists(".testing.coverage", "Coverage data not collected in CI")
