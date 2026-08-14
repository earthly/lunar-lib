from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("min-participants", "On-call rotation has enough participants", node=node)
    with c:
        min_required = int(variable_or_default("min_participants", "2"))

        # See schedule_configured.py for why these two gates exist: without
        # them, "no on-call tool connected" and "the collector bailed out"
        # both render as "your rotation has nobody in it".
        source = c.get_node(".oncall.source")
        if not source.exists():
            c.skip("No on-call tool has written data for this component")

        if not c.get_node(".oncall.summary").exists():
            c.fail(
                "The on-call collector did not finish, so the rotation is "
                "unknown. Check the collector's API credentials and that this "
                "component maps to a service in your on-call tool."
            )
            return c

        participants_node = c.get_node(".oncall.schedule.participants")
        if not participants_node.exists():
            c.fail(
                f"On-call rotation has no participants configured; at least "
                f"{min_required} required. Add people to your rotation to "
                f"avoid single-person burnout and coverage gaps."
            )
        else:
            participants = int(participants_node.get_value())
            c.assert_true(
                participants >= min_required,
                f"On-call rotation has {participants} participant(s); "
                f"at least {min_required} required. Add more people to the "
                f"rotation to avoid single-person burnout and coverage gaps.",
            )
    return c


if __name__ == "__main__":
    main()
