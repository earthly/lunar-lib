from lunar_policy import Check, variable_or_default


def main(node=None, required_sections_override=None):
    c = Check("dr-plan-required-sections", "DR plan should contain required sections", node=node)
    with c:
        required_str = required_sections_override if required_sections_override is not None \
            else variable_or_default("plan_required_sections", "")
        if not required_str:
            c.skip()

        required_sections = [s.strip() for s in required_str.split(",") if s.strip()]

        plan = c.get_node(".oncall.disaster_recovery.plan")
        if not plan.exists():
            c.fail("DR plan data not found. Ensure the dr-docs collector is configured and has run.")
            return c

        if not plan.get_value_or_default(".exists", False):
            c.fail("DR plan not found — cannot verify sections")
            return c

        sections = plan.get_value_or_default(".sections", [])
        sections_lower = [s.lower() for s in sections]

        missing = [s for s in required_sections if s.lower() not in sections_lower]

        if missing:
            c.fail(f"DR plan is missing required sections: {', '.join(missing)}")
    return c


if __name__ == "__main__":
    main()
