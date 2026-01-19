from lunar_policy import Check, variable_or_default


def main():
    with Check("minimum-approvals", "Pull requests should require minimum number of approvals") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        min_approvals = variable_or_default("min_approvals", None)
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


if __name__ == "__main__":
    main()
