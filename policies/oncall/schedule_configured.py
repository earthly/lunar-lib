from lunar_policy import Check


def main(node=None):
    c = Check("schedule-configured", "Service has an on-call schedule", node=node)
    with c:
        schedule_node = c.get_node(".oncall.schedule.exists")
        c.assert_true(
            schedule_node.exists() and bool(schedule_node.get_value()),
            "Service has no on-call schedule configured. Set up a schedule "
            "in your on-call tool (PagerDuty, OpsGenie, etc.) and attach "
            "it to the service's escalation policy.",
        )
    return c


if __name__ == "__main__":
    main()
