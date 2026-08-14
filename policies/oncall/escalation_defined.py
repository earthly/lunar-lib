from lunar_policy import Check


def main(node=None):
    c = Check("escalation-defined", "Service has an escalation policy", node=node)
    with c:
        # See schedule_configured.py for why these two gates exist: without
        # them, "no on-call tool connected" and "the collector bailed out"
        # both render as "you have no escalation policy".
        source = c.get_node(".oncall.source")
        if not source.exists():
            c.skip("No on-call tool has written data for this component")

        if not c.get_node(".oncall.summary").exists():
            c.fail(
                "The on-call collector did not finish, so the escalation "
                "policy is unknown. Check the collector's API credentials and "
                "that this component maps to a service in your on-call tool."
            )
            return c

        escalation_node = c.get_node(".oncall.escalation.exists")
        c.assert_true(
            escalation_node.exists() and bool(escalation_node.get_value()),
            "Service has no escalation policy configured. Define an "
            "escalation policy in your on-call tool so incidents can be "
            "escalated when the primary responder does not acknowledge.",
        )
    return c


if __name__ == "__main__":
    main()
