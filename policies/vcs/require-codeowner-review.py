from lunar_policy import Check


def main():
    with Check("require-codeowner-review", "Code owner review should be required") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.skip("Branch protection is not enabled")

        require_codeowner_review = c.get_value(".vcs.branch_protection.require_codeowner_review")
        if not require_codeowner_review:
            c.fail("Branch protection does not require code owner review")


if __name__ == "__main__":
    main()
