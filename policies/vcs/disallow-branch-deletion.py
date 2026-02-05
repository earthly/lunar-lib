from lunar_policy import Check


def main(node=None):
    c = Check("disallow-branch-deletion", "Branch deletions should be disallowed", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail("Branch protection is not enabled")
        else:
            allow_deletions = c.get_value(".vcs.branch_protection.allow_deletions")
            c.assert_false(allow_deletions, "Branch protection allows branch deletion, but policy requires it to be disabled")
    return c


if __name__ == "__main__":
    main()
