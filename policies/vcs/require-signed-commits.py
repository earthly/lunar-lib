from lunar_policy import Check


def main(node=None):
    c = Check("require-signed-commits", "Signed commits should be required", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail("Branch protection is not enabled")
        else:
            require_signed_commits = c.get_value(".vcs.branch_protection.require_signed_commits")
            c.assert_true(require_signed_commits, "Branch protection does not require signed commits")
    return c


if __name__ == "__main__":
    main()
