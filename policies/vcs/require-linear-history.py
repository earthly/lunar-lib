from lunar_policy import Check


def main():
    with Check("require-linear-history", "Linear history should be required") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        has_linear_history = bp.get_value_or_default(".require_linear_history", False)
        if not has_linear_history:
            c.fail("Branch protection does not require linear history")


if __name__ == "__main__":
    main()
