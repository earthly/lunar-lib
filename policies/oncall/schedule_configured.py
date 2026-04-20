from lunar_policy import Check


def main(node=None):
    c = Check("schedule-configured", "Service has an on-call schedule", node=node)
    with c:
        oncall_source = c.get_node(".oncall.source")
        if not oncall_source.exists():
            c.skip("No oncall source data — collector has not run or produced no data")

        exists = c.get_value_or_default(".oncall.schedule.exists", False)
        c.assert_true(
            bool(exists),
            "Service has no on-call schedule configured. Set up a schedule "
            "in your on-call tool and attach it to the service's escalation "
            "policy.",
        )
    return c


if __name__ == "__main__":
    main()
