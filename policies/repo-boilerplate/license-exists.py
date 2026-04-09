from lunar_policy import Check

with Check("license-exists", "Repository should have a LICENSE file") as c:
    c.assert_true(
        c.get_value(".repo.license.exists"),
        "No LICENSE file found. Add a LICENSE file to define how your code may be used.",
    )
