from datetime import date, datetime

from lunar_policy import Check, variable_or_default


def _days_since(date_str):
    """Compute days elapsed since a YYYY-MM-DD date string."""
    d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    return (date.today() - d).days


def main(node=None, max_days_override=None):
    c = Check("dr-exercise-recent", "DR exercise should be conducted regularly", node=node)
    with c:
        max_days_str = max_days_override if max_days_override is not None \
            else variable_or_default("max_days_since_exercise", "365")
        try:
            max_days = int(max_days_str)
        except (ValueError, TypeError):
            raise ValueError(
                f"Policy misconfiguration: 'max_days_since_exercise' must be a number, got '{max_days_str}'"
            )
        if max_days <= 0:
            raise ValueError(
                f"Policy misconfiguration: 'max_days_since_exercise' must be > 0, got {max_days}"
            )

        dr = c.get_node(".oncall.disaster_recovery")
        if not dr.exists():
            c.fail("DR data not found. Ensure the dr-docs collector is configured and has run.")
            return c

        count = dr.get_value_or_default(".exercise_count", 0)
        if count == 0:
            c.fail("No DR exercise records found — create docs/dr-exercises/YYYY-MM-DD.md")
            return c

        latest = dr.get_value_or_default(".latest_exercise_date", "")
        if not latest:
            c.fail("No DR exercise date could be determined")
            return c

        # Compute freshness at evaluation time, not collection time
        days = _days_since(latest)
        c.assert_less_or_equal(days, max_days,
            f"Last DR exercise was {days} days ago (maximum allowed: {max_days})")
    return c


if __name__ == "__main__":
    main()
