from lunar_policy import Check

with Check("codeowners-exists", "Repository should have a CODEOWNERS file") as c:
    node = c.get_node(".ownership.codeowners.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No CODEOWNERS file found. Add a CODEOWNERS file to the repository root, .github/, or docs/ directory.",
    )
