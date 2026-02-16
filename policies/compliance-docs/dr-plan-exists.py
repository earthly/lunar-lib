from lunar_policy import Check


def main(node=None):
    c = Check("dr-plan-exists", "DR plan document should exist", node=node)
    with c:
        plan = c.get_node(".oncall.disaster_recovery.plan")
        if not plan.exists():
            c.fail("DR plan data not found. Ensure the dr-docs collector is configured and has run.")
            return c

        exists = plan.get_value_or_default(".exists", False)
        path = plan.get_value_or_default(".path", "docs/dr-plan.md")
        c.assert_true(exists, f"DR plan not found (expected {path})")
    return c


if __name__ == "__main__":
    main()
