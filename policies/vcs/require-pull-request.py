from lunar_policy import Check


def main():
    with Check("require-pull-request", "Pull requests should be required") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        has_pr_requirement = bp.get_value_or_default(".require_pr", False)
        if not has_pr_requirement:
            c.fail("Branch protection does not require pull requests before merging")


if __name__ == "__main__":
    main()
