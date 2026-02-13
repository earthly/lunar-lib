from lunar_policy import Check


def main(node=None):
    c = Check("dr-plan-exists", "DR plan document should exist", node=node)
    with c:
        c.assert_exists(".oncall.disaster_recovery.plan",
            "DR plan data not found. Ensure the dr-docs collector is configured and has run.")

        exists = c.get_value(".oncall.disaster_recovery.plan.exists")
        path = c.get_value_or_default(".oncall.disaster_recovery.plan.path", "docs/dr-plan.md")
        c.assert_true(exists, f"DR plan not found (expected {path})")
    return c


if __name__ == "__main__":
    main()
