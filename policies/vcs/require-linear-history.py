from lunar_policy import Check


def main(node=None):
    c = Check("require-linear-history", "Linear history should be required", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        require_linear_history = c.get_value(".vcs.branch_protection.require_linear_history")
        c.assert_true(require_linear_history, "Branch protection does not require linear history")
    return c


if __name__ == "__main__":
    main()
