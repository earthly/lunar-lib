from lunar_policy import Check

with Check("reported", "Coverage percentage should be reported") as c:
    c.assert_exists(".testing.coverage.percentage", "Coverage percentage not reported")
