from lunar_policy import Check


def main():
    with Check("branch-protection-enabled", "Branch protection should be enabled") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        branch = c.get_value_or_default(".vcs.branch_protection.branch", "default branch")

        if not enabled:
            c.fail(f"Branch protection is not enabled on {branch}")


if __name__ == "__main__":
    main()
