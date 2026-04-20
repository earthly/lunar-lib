from lunar_policy import Check


def main(node=None):
    c = Check("escalation-defined", "Service has an escalation policy", node=node)
    with c:
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
