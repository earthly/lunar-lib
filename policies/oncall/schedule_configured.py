from lunar_policy import Check


def main(node=None):
    c = Check("schedule-configured", "Service has an on-call schedule", node=node)
    with c:
        # No on-call tool is wired up for this component at all, so the check
        # does not apply. Without this gate that state is indistinguishable
        # from "the tool says there is no schedule", and the component gets
        # told to configure a rotation in a tool it does not use.
        source = c.get_node(".oncall.source")
        if not source.exists():
            c.skip("No on-call tool has written data for this component")

        # .oncall.summary is the collector's final write, so its absence means
        # the run bailed out rather than reporting a service without a
        # schedule. Both the pagerduty and opsgenie collectors exit 0 on a
        # missing token, an unresolved service, or an API error -- and the
        # pagerduty one does so *after* .oncall.source is written, which is
        # exactly the shape that produced a false "no schedule configured".
        if not c.get_node(".oncall.summary").exists():
            c.fail(
                "The on-call collector did not finish, so the schedule is "
                "unknown. Check the collector's API credentials and that this "
                "component maps to a service in your on-call tool."
            )
            return c

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
