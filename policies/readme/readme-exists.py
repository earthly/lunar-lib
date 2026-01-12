from lunar_policy import Check

with Check("readme-exists", "Repository should have a README file") as c:
    readme = c.get_node(".repo.readme")
    
    # Note that the collector should always write exists = true/false, 
    # so readme.exists() should always pass as long as the collector is configured.
    if readme.exists():
        exists = readme.get_value_or_default(".exists", False)
        c.assert_true(exists, "README file not found")
