from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("min-participants", "On-call rotation has enough participants", node=node)
    with c:
        oncall_source = c.get_node(".oncall.source")
        if not oncall_source.exists():
            c.skip("No oncall source data — collector has not run or produced no data")

        if not c.get_value_or_default(".oncall.schedule.exists", False):
            c.skip("No on-call schedule — covered by schedule-configured check")

        try:
            min_required = int(variable_or_default("min_participants", "2"))
        except ValueError:
            c.skip("Invalid min_participants configuration")

        participants = int(c.get_value_or_default(".oncall.schedule.participants", 0))

        c.assert_true(
            participants >= min_required,
            f"On-call rotation has {participants} participant(s); "
            f"at least {min_required} required. Add more people to the "
            f"rotation to avoid single-person burnout and coverage gaps.",
        )
    return c


if __name__ == "__main__":
    main()
