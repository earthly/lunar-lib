from lunar_policy import Check

with Check("readme-exists", "Repository should have a README.md file") as c:
    readme = c.get_node(".repo.readme")
    
    if readme.exists():
        exists = readme.get_value_or_default(".exists", False)
        c.assert_true(exists, "README.md file not found")
