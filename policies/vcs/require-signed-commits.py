from lunar_policy import Check


def main():
    with Check("require-signed-commits", "Signed commits should be required") as c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        require_signed_commits = c.get_value(".vcs.branch_protection.require_signed_commits")
        c.assert_true(require_signed_commits, "Branch protection does not require signed commits")


if __name__ == "__main__":
    main()
