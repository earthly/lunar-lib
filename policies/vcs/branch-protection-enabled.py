from lunar_policy import Check


def main():
    with Check("branch-protection-enabled", "Branch protection should be enabled") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        enabled = bp.get_value_or_default(".enabled", False)
        branch = bp.get_value_or_default(".branch", "default branch")

        if not enabled:
            c.fail(f"Branch protection is not enabled on {branch}")


if __name__ == "__main__":
    main()
