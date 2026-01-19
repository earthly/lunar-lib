from lunar_policy import Check


def main():
    with Check("require-status-checks", "Status checks should be required") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        require_status_checks = c.get_value(".vcs.branch_protection.require_status_checks")
        c.assert_true(require_status_checks, "Branch protection does not require status checks to pass")


if __name__ == "__main__":
    main()
