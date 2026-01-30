from lunar_policy import Check


def main(node=None):
    c = Check("require-codeowner-review", "Code owner review should be required", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail("Branch protection is not enabled")
        else:
            require_codeowner_review = c.get_value(".vcs.branch_protection.require_codeowner_review")
            c.assert_true(require_codeowner_review, "Branch protection does not require code owner review")
    return c


if __name__ == "__main__":
    main()
