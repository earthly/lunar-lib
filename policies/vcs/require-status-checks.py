from lunar_policy import Check


def main():
    with Check("require-status-checks", "Status checks should be required") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.skip("Branch protection is not enabled")

        require_status_checks = c.get_value(".vcs.branch_protection.require_status_checks")
        if not require_status_checks:
            c.fail("Branch protection does not require status checks to pass")


if __name__ == "__main__":
    main()
