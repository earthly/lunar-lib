from lunar_policy import Check


def main():
    with Check("require-codeowner-review", "Code owner review should be required") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        has_codeowner_review = bp.get_value_or_default(".require_codeowner_review", False)
        if not has_codeowner_review:
            c.fail("Branch protection does not require code owner review")


if __name__ == "__main__":
    main()
