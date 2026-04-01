from lunar_policy import Check

with Check("spec-valid", "All API spec files should be syntactically valid") as c:
    specs = c.get_node(".api.specs")
    if not specs.exists():
        c.skip("No API spec files detected")

    for spec in specs:
        path = spec.get_value_or_default(".path", "<unknown>")
        valid = spec.get_value_or_default(".valid", False)
        c.assert_true(valid, f"{path}: spec file failed to parse")
