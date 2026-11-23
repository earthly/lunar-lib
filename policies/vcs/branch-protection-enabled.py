from lunar_policy import Check

from settings_hint import BRANCH_PROTECTION, with_hint


def main(node=None):
    c = Check("branch-protection-enabled", "Branch protection should be enabled", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure a VCS collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        branch = c.get_value_or_default(".vcs.branch_protection.branch", "default branch")

        c.assert_true(enabled, with_hint(
            c, f"Branch protection is not enabled on {branch}",
            BRANCH_PROTECTION))
    return c


if __name__ == "__main__":
    main()
