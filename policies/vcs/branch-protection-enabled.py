from lunar_policy import Check


def main(node=None):
    c = Check("branch-protection-enabled", "Branch protection should be enabled", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        branch = c.get_value_or_default(".vcs.branch_protection.branch", "default branch")

        c.assert_true(enabled, f"Branch protection is not enabled on {branch}")
    return c


if __name__ == "__main__":
    main()
