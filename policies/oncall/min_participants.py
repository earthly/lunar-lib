from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("min-participants", "On-call rotation has enough participants", node=node)
    with c:
        min_required = int(variable_or_default("min_participants", "2"))

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
