from lunar_policy import Check


def main(node=None):
    c = Check("escalation-defined", "Service has an escalation policy", node=node)
    with c:
        oncall_source = c.get_node(".oncall.source")
        if not oncall_source.exists():
            c.skip("No oncall source data — collector has not run or produced no data")

        exists = c.get_value_or_default(".oncall.escalation.exists", False)
        c.assert_true(
            bool(exists),
            "Service has no escalation policy configured. Define an "
            "escalation policy in your on-call tool so incidents can be "
            "escalated when the primary responder does not acknowledge.",
        )
    return c


if __name__ == "__main__":
    main()
