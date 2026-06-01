from lunar_policy import Check

with Check("security-exists", "Repository should have a SECURITY.md file") as c:
    node = c.get_node(".repo.security.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No SECURITY.md file found. Add a SECURITY.md to provide a vulnerability disclosure channel.",
    )
