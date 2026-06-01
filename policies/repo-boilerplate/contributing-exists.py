from lunar_policy import Check

with Check("contributing-exists", "Repository should have a CONTRIBUTING.md file") as c:
    node = c.get_node(".repo.contributing.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No CONTRIBUTING.md file found. Add a CONTRIBUTING.md to help contributors understand the process.",
    )
