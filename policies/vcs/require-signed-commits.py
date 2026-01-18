from lunar_policy import Check


def main():
    with Check("require-signed-commits", "Signed commits should be required") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        has_signed_commits = bp.get_value_or_default(".require_signed_commits", False)
        if not has_signed_commits:
            c.fail("Branch protection does not require signed commits")


if __name__ == "__main__":
    main()
