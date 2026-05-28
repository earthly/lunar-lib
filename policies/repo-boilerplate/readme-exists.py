from lunar_policy import Check

with Check("readme-exists", "Repository should have a README file") as c:
    node = c.get_node(".repo.readme.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No README file found. Add a README.md to describe the project and how to use it.",
    )
