from lunar_policy import Check

with Check("contributing-exists", "Repository should have a CONTRIBUTING.md file") as c:
    c.assert_true(
        c.get_value(".repo.contributing.exists"),
        "No CONTRIBUTING.md file found. Add a CONTRIBUTING.md to help contributors understand the process.",
    )
