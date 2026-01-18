from lunar_policy import Check


def main():
    with Check("disallow-force-push", "Force pushes should be disallowed") as c:
        bp = c.get_node(".vcs.branch_protection")

        if not bp.exists():
            c.skip("No branch protection data collected")

        if not bp.get_value_or_default(".enabled", False):
            c.skip("Branch protection is not enabled")

        allows_force_push = bp.get_value_or_default(".allow_force_push", False)
        if allows_force_push:
            c.fail("Branch protection allows force pushes, but policy requires them to be disabled")


if __name__ == "__main__":
    main()
