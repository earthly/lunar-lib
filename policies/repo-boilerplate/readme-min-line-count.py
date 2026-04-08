from lunar_policy import Check, variable_or_default

with Check("readme-min-line-count", "README file should have minimum line count") as c:
    readme = c.get_node(".repo.readme")

    min_lines = int(variable_or_default("min_lines", "25"))
    if min_lines == 0:
        c.skip()

    lines = readme.get_value_or_default(".lines", 0)

    c.assert_greater_or_equal(
        lines,
        min_lines,
        f"README file has {lines} lines, but minimum required is {min_lines}",
    )
