from lunar_policy import Check, variable_or_default


def main(node=None, max_days_override=None):
    c = Check("dr-exercise-recent", "DR exercise should be conducted regularly", node=node)
    with c:
        max_days = int(max_days_override or variable_or_default("max_days_since_exercise", "365"))

        dr = c.get_node(".oncall.disaster_recovery")
        c.assert_exists(".oncall.disaster_recovery",
            "DR data not found. Ensure the dr-docs collector is configured and has run.")

        count = dr.get_value_or_default(".exercise_count", 0)
        if count == 0:
            c.fail("No DR exercise records found — create docs/dr-exercises/YYYY-MM-DD.md")
            return c

        latest = dr.get_value_or_default(".latest_exercise_date", "")
        if not latest:
            c.fail("No DR exercise date could be determined")
            return c

        days = dr.get_value(".days_since_latest_exercise")
        c.assert_less_or_equal(days, max_days,
            f"Last DR exercise was {days} days ago (maximum allowed: {max_days})")
    return c


if __name__ == "__main__":
    main()
