from lunar_policy import Check


def main(node=None):
    c = Check("disallow-force-push", "Force pushes should be disallowed", node=node)
    with c:
        c.assert_exists(".vcs.branch_protection", 
            "VCS data not found. Ensure the github collector is configured and has run.")
        
        enabled = c.get_value(".vcs.branch_protection.enabled")
        c.assert_true(enabled, "Branch protection is not enabled")

        allow_force_push = c.get_value(".vcs.branch_protection.allow_force_push")
        c.assert_false(allow_force_push, "Branch protection allows force pushes, but policy requires them to be disabled")
    return c


if __name__ == "__main__":
    main()
