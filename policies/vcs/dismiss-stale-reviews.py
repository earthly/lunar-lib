from lunar_policy import Check


def main():
    with Check("dismiss-stale-reviews", "Stale reviews should be dismissed") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        dismiss_stale_reviews = c.get_value(".vcs.branch_protection.dismiss_stale_reviews")
        c.assert_true(dismiss_stale_reviews, "Branch protection does not dismiss stale reviews when new commits are pushed")


if __name__ == "__main__":
    main()
