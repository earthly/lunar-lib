from lunar_policy import Check

with Check("gitignore-exists", "Repository should have a .gitignore file") as c:
    node = c.get_node(".repo.gitignore.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No .gitignore file found. Add a .gitignore to prevent accidental commits of build artifacts and dependencies.",
    )
