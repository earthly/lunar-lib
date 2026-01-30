from lunar_policy import Check


def main(node=None):
    c = Check("require-branches-up-to-date", "Branches should be required to be up to date", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        require_branches_up_to_date = c.get_value(".vcs.branch_protection.require_branches_up_to_date")
        c.assert_true(require_branches_up_to_date, "Branch protection does not require branches to be up to date before merging")
    return c


if __name__ == "__main__":
    main()
