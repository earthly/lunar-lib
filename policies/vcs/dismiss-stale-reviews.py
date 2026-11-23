from lunar_policy import Check

from settings_hint import BRANCH_PROTECTION, with_hint


def main(node=None):
    c = Check("dismiss-stale-reviews", "Stale reviews should be dismissed", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail(with_hint(c, "Branch protection is not enabled", BRANCH_PROTECTION))
            return c
        else:
            dismiss_stale_reviews = c.get_value(".vcs.branch_protection.dismiss_stale_reviews")
            c.assert_true(dismiss_stale_reviews, with_hint(
                c, "Branch protection does not dismiss stale reviews when new commits are pushed",
                BRANCH_PROTECTION))
    return c


if __name__ == "__main__":
    main()
