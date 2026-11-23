from lunar_policy import Check

from settings_hint import BRANCH_PROTECTION, with_hint


def main(node=None):
    c = Check("disallow-branch-deletion", "Branch deletions should be disallowed", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail(with_hint(c, "Branch protection is not enabled", BRANCH_PROTECTION))
            return c
        else:
            allow_deletions = c.get_value(".vcs.branch_protection.allow_deletions")
            c.assert_false(allow_deletions, with_hint(
                c, "Branch protection allows branch deletion, but policy requires it to be disabled",
                BRANCH_PROTECTION))
    return c


if __name__ == "__main__":
    main()
