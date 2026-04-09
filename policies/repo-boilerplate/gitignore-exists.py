from lunar_policy import Check

with Check("gitignore-exists", "Repository should have a .gitignore file") as c:
    c.assert_true(
        c.get_value(".repo.gitignore.exists"),
        "No .gitignore file found. Add a .gitignore to prevent accidental commits of build artifacts and dependencies.",
    )
