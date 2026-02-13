from lunar_policy import Check


def main(node=None):
    c = Check("dr-plan-rto-rpo-defined", "Recovery objectives (RTO/RPO) should be defined in DR plan", node=node)
    with c:
        plan = c.get_node(".oncall.disaster_recovery.plan")
        if not plan.exists():
            c.fail("DR plan data not found. Ensure the dr-docs collector is configured and has run.")
            return c

        if not plan.get_value_or_default(".exists", False):
            c.fail("DR plan not found — cannot verify recovery objectives")
            return c

        rto = plan.get_value_or_default(".rto_defined", False)
        rpo = plan.get_value_or_default(".rpo_defined", False)

        if not rto and not rpo:
            c.fail("Recovery objectives not defined — add rto_minutes and rpo_minutes to DR plan frontmatter")
        elif not rto:
            c.fail("RTO not defined — add rto_minutes to DR plan frontmatter")
        elif not rpo:
            c.fail("RPO not defined — add rpo_minutes to DR plan frontmatter")
    return c


if __name__ == "__main__":
    main()
