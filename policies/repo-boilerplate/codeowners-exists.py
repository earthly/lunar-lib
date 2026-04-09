from lunar_policy import Check

with Check("codeowners-exists", "Repository should have a CODEOWNERS file") as c:
    c.assert_true(
        c.get_value(".ownership.codeowners.exists"),
        "No CODEOWNERS file found. Add a CODEOWNERS file to the repository root, .github/, or docs/ directory.",
    )
