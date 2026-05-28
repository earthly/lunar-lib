from lunar_policy import Check

with Check("editorconfig-exists", "Repository should have an .editorconfig file") as c:
    node = c.get_node(".repo.editorconfig.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No .editorconfig file found. Add an .editorconfig to ensure consistent coding style across editors.",
    )
