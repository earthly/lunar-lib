from lunar_policy import Check, variable_or_default

with Check("readme-min-line-count", "README file should have minimum line count") as c:
    readme = c.get_node(".repo.readme")

    if not readme.exists():
        c.skip()
    
    # Skip if no minimum line count is configured
    min_lines = int(variable_or_default("min_lines", "0"))
    if min_lines == 0:
        c.skip()

    # Get number of lines in README file from collector data
    lines = readme.get_value_or_default(".lines", 0)
    
    c.assert_greater_or_equal(
        lines,
        min_lines,
        f"README file has {lines} lines, but minimum required is {min_lines}"
    )
