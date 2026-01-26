from lunar_policy import Check, variable_or_default

with Check("min-coverage", "Code coverage should meet minimum threshold") as c:
    min_coverage = int(variable_or_default("min_coverage", "80"))
    coverage = c.get_value(".testing.codecov.results.coverage")
    c.assert_greater_or_equal(
        coverage,
        min_coverage,
        f"Coverage {coverage}% is below minimum {min_coverage}%"
    )
