from lunar_policy import Check

with Check("license-exists", "Repository should have a LICENSE file") as c:
    node = c.get_node(".repo.license.exists")
    c.assert_true(
        node.exists() and bool(node.get_value()),
        "No LICENSE file found. Add a LICENSE file to define how your code may be used.",
    )
