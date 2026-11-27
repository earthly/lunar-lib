from lunar_policy import Check

from settings_hint import BRANCH_PROTECTION, with_hint


def main(node=None):
    c = Check("require-signed-commits", "Signed commits should be required", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail(with_hint(c, "Branch protection is not enabled", BRANCH_PROTECTION))
            return c
        else:
            require_signed_commits = c.get_value(".vcs.branch_protection.require_signed_commits")
            c.assert_true(require_signed_commits, with_hint(
                c, "Branch protection does not require signed commits",
                BRANCH_PROTECTION))
    return c


if __name__ == "__main__":
    main()
