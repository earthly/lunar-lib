from lunar_policy import Check


def main():
    with Check("dismiss-stale-reviews", "Stale reviews should be dismissed") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        dismisses_stale = bp.get_value_or_default(".dismiss_stale_reviews", False)
        if not dismisses_stale:
            c.fail("Branch protection does not dismiss stale reviews when new commits are pushed")


if __name__ == "__main__":
    main()
