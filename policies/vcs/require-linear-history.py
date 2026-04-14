from lunar_policy import Check


def main(node=None):
    c = Check("require-linear-history", "Linear history should be required", node=node)
    with c:
        if not c.get_node(".vcs.branch_protection").exists():
            c.fail("VCS data not found. Ensure the github collector is configured and has run.")
            return c

        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.fail("Branch protection is not enabled")
            return c
        else:
            require_linear_history = c.get_value(".vcs.branch_protection.require_linear_history")
            c.assert_true(require_linear_history, "Branch protection does not require linear history")
    return c


if __name__ == "__main__":
    main()
