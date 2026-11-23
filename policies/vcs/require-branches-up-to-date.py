from lunar_policy import Check

from settings_hint import BRANCH_PROTECTION, with_hint


def main(node=None):
    c = Check("require-branches-up-to-date", "Branches should be required to be up to date", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail(with_hint(c, "Branch protection is not enabled", BRANCH_PROTECTION))
            return c
        else:
            require_branches_up_to_date = c.get_value(".vcs.branch_protection.require_branches_up_to_date")
            c.assert_true(require_branches_up_to_date, with_hint(
                c, "Branch protection does not require branches to be up to date before merging",
                BRANCH_PROTECTION))
    return c


if __name__ == "__main__":
    main()
