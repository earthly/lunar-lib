from lunar_policy import Check


def main(node=None):
    c = Check("require-pull-request", "Pull requests should be required", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        require_pr = c.get_value(".vcs.branch_protection.require_pr")
        c.assert_true(require_pr, "Branch protection does not require pull requests before merging")
    return c


if __name__ == "__main__":
    main()
