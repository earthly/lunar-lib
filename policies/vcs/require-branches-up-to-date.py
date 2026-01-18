from lunar_policy import Check


def main():
    with Check("require-branches-up-to-date", "Branches should be required to be up to date") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        branches_up_to_date = bp.get_value_or_default(".require_branches_up_to_date", False)
        if not branches_up_to_date:
            c.fail("Branch protection does not require branches to be up to date before merging")


if __name__ == "__main__":
    main()
