from lunar_policy import Check


def main():
    with Check("require-linear-history", "Linear history should be required") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.skip("Branch protection is not enabled")

        require_linear_history = c.get_value(".vcs.branch_protection.require_linear_history")
        if not require_linear_history:
            c.fail("Branch protection does not require linear history")


if __name__ == "__main__":
    main()
