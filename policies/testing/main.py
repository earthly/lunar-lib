from lunar_policy import Check, variable_or_default

with Check("coverage", "Has Minimum Test Coverage") as c:
    # Check if coverage data exists in the standardized .testing.coverage location
    if c.exists(".testing.coverage"):
        min_coverage = float(variable_or_default("min_coverage", "0"))
        coverage_pct = c.get_value(".testing.coverage.percentage")
        
        if coverage_pct is not None:
            c.assert_greater_or_equal(
                coverage_pct,
                min_coverage,
                f"Test coverage {coverage_pct}% is below minimum required {min_coverage}%"
            )
        else:
            c.assert_true(False, "Test coverage percentage was not reported")
    else:
        c.assert_true(False, "Test coverage data was not collected")
