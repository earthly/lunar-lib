from lunar_policy import Check


def main():
    with Check("require-pull-request", "Pull requests should be required") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        require_pr = c.get_value(".vcs.branch_protection.require_pr")
        c.assert_true(require_pr, "Branch protection does not require pull requests before merging")


if __name__ == "__main__":
    main()
