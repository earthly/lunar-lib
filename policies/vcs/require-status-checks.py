from lunar_policy import Check


def main():
    with Check("require-status-checks", "Status checks should be required") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        has_status_checks = bp.get_value_or_default(".require_status_checks", False)
        if not has_status_checks:
            c.fail("Branch protection does not require status checks to pass")


if __name__ == "__main__":
    main()
