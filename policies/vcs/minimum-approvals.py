from lunar_policy import Check, variable_or_default


def main(node=None, min_approvals_override=None):
    c = Check("minimum-approvals", "Pull requests should require minimum number of approvals", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        min_approvals = min_approvals_override if min_approvals_override is not None else variable_or_default("min_approvals", None)
        if min_approvals is None:
            raise ValueError("Policy misconfiguration: min_approvals must be configured")

        try:
            min_approvals = int(min_approvals)
        except (ValueError, TypeError):
            raise ValueError(f"Policy misconfiguration: min_approvals must be a number, got: {min_approvals}")

        required_approvals = c.get_value(".vcs.branch_protection.required_approvals")
        c.assert_greater_or_equal(
            required_approvals,
            min_approvals,
            f"Branch protection requires {required_approvals} approval(s), "
            f"but policy requires at least {min_approvals}"
        )
    return c


if __name__ == "__main__":
    main()
