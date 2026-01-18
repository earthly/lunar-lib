from lunar_policy import Check


def main():
    with Check("disallow-force-push", "Force pushes should be disallowed") as c:
        enabled = c.get_value(".vcs.branch_protection.enabled")
        if not enabled:
            c.skip("Branch protection is not enabled")

        allow_force_push = c.get_value(".vcs.branch_protection.allow_force_push")
        if allow_force_push:
            c.fail("Branch protection allows force pushes, but policy requires them to be disabled")


if __name__ == "__main__":
    main()
