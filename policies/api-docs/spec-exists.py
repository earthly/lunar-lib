from lunar_policy import Check

with Check("spec-exists", "Repository should have at least one API spec file") as c:
    specs = c.get_node(".api.specs")
    if not specs.exists():
        c.skip("No API spec collectors have run (enable the openapi or swagger collector)")

    count = 0
    for _ in specs:
        count += 1

    c.assert_true(count > 0, "No API spec files found — add an openapi.yaml or swagger.json")
