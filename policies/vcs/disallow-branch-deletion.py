from lunar_policy import Check


def main():
    with Check("disallow-branch-deletion", "Branch deletions should be disallowed") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.skip("Branch protection is not enabled")

        allow_deletions = c.get_value(".vcs.branch_protection.allow_deletions")
        if allow_deletions:
            c.fail("Branch protection allows branch deletion, but policy requires it to be disabled")


if __name__ == "__main__":
    main()
