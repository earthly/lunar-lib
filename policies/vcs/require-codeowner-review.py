from lunar_policy import Check

from settings_hint import BRANCH_PROTECTION, with_hint


def main(node=None):
    c = Check("require-codeowner-review", "Code owner review should be required", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail(with_hint(c, "Branch protection is not enabled", BRANCH_PROTECTION))
            return c
        else:
            require_codeowner_review = c.get_value(".vcs.branch_protection.require_codeowner_review")
            c.assert_true(require_codeowner_review, with_hint(
                c, "Branch protection does not require code owner review",
                BRANCH_PROTECTION))
    return c


if __name__ == "__main__":
    main()
