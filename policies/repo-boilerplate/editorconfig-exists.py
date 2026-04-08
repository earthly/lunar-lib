from lunar_policy import Check

with Check("editorconfig-exists", "Repository should have an .editorconfig file") as c:
    c.assert_true(
        c.get_value(".repo.editorconfig.exists"),
        "No .editorconfig file found. Add an .editorconfig to ensure consistent coding style across editors.",
    )
