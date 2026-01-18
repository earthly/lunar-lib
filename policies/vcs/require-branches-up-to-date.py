from lunar_policy import Check


def main():
    with Check("require-branches-up-to-date", "Branches should be required to be up to date") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.skip("Branch protection is not enabled")

        require_branches_up_to_date = c.get_value(".vcs.branch_protection.require_branches_up_to_date")
        c.assert_true(require_branches_up_to_date, "Branch protection does not require branches to be up to date before merging")


if __name__ == "__main__":
    main()
