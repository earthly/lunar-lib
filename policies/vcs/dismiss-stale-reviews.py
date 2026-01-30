from lunar_policy import Check


def main(node=None):
    c = Check("dismiss-stale-reviews", "Stale reviews should be dismissed", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        dismiss_stale_reviews = c.get_value(".vcs.branch_protection.dismiss_stale_reviews")
        c.assert_true(dismiss_stale_reviews, "Branch protection does not dismiss stale reviews when new commits are pushed")
    return c


if __name__ == "__main__":
    main()
