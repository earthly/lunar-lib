from lunar_policy import Check


def main():
    with Check("disallow-branch-deletion", "Branch deletions should be disallowed") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        allows_deletions = bp.get_value_or_default(".allow_deletions", False)
        if allows_deletions:
            c.fail("Branch protection allows branch deletion, but policy requires it to be disabled")


if __name__ == "__main__":
    main()
