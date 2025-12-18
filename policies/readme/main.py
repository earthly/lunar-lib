from lunar_policy import Check

with Check("readme-exists", "Repository should have a README.md file") as c:
    if not c.get_node(".repo.readme_exists").exists():
        c.fail("README.md file not found")
