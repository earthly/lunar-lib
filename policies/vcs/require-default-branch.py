from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("require-default-branch", "Default branch should match required name", node=node)
    with c:
        c.assert_exists(".vcs.default_branch", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        required_default_branch = variable_or_default("required_default_branch", "main")
        default_branch = c.get_value(".vcs.default_branch")

        c.assert_equals(default_branch, required_default_branch, f"Default branch is '{default_branch}', but policy requires '{required_default_branch}'")
    return c


if __name__ == "__main__":
    main()
