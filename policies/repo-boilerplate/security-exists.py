from lunar_policy import Check

with Check("security-exists", "Repository should have a SECURITY.md file") as c:
    c.assert_true(
        c.get_value(".repo.security.exists"),
        "No SECURITY.md file found. Add a SECURITY.md to provide a vulnerability disclosure channel.",
    )
