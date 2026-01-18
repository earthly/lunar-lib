from lunar_policy import Check, variable_or_default


def main():
    with Check("minimum-approvals", "Pull requests should require minimum number of approvals") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        min_approvals = variable_or_default("min_approvals", None)
        if min_approvals is None:
            c.skip("min_approvals not configured")

        try:
            min_approvals = int(min_approvals)
            required_approvals = bp.get_value_or_default(".required_approvals", 0)
            if required_approvals < min_approvals:
                c.fail(
                    f"Branch protection requires {required_approvals} approval(s), "
                    f"but policy requires at least {min_approvals}"
                )
        except (ValueError, TypeError):
            raise ValueError(f"min_approvals must be a number, got: {min_approvals}")


if __name__ == "__main__":
    main()
