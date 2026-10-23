"""Score a component on the share of its recent pull requests that referenced a ticket.

Reads `.vcs.ticket_coverage`, written on the default branch by the ticket-coverage
collector, and fails when the percentage falls below `min_percentage`.

Two results are deliberately not failures: no coverage data collected yet, and a window
containing no pull requests at all. A component that has not changed recently has not
violated a change-management control.
"""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check(
        "ticket-coverage",
        "A high share of recent pull requests should reference a ticket",
        node=node,
    )
    with c:
        coverage = c.get_node(".vcs.ticket_coverage")
        if not coverage.exists():
            # Absent on pull requests and before the collector's first default-branch
            # run. get_node().exists() returns a bool; c.exists() would raise NoDataError
            # and make the skip below unreachable.
            c.skip("No ticket coverage data yet (default-branch metric)")

        window = coverage.get_value_or_default(".window_days", 30)
        prs_total = coverage.get_value_or_default(".prs_total", 0)
        prs_with_ticket = coverage.get_value_or_default(".prs_with_ticket", 0)
        percentage = coverage.get_value_or_default(".percentage", None)

        if not prs_total or percentage is None:
            c.skip(f"No pull requests in the last {window}d to assess")

        raw_minimum = variable_or_default("min_percentage", "80")
        try:
            minimum = float(raw_minimum)
        except (TypeError, ValueError):
            raise ValueError(
                f"Policy misconfiguration: 'min_percentage' must be a number, got '{raw_minimum}'"
            )
        if not 0 <= minimum <= 100:
            raise ValueError(
                f"Policy misconfiguration: 'min_percentage' must be between 0 and 100, got '{raw_minimum}'"
            )

        c.assert_true(
            float(percentage) >= minimum,
            f"Only {percentage}% of pull requests in the last {window}d referenced a "
            f"ticket ({prs_with_ticket}/{prs_total}); minimum is {minimum}%.",
        )


if __name__ == "__main__":
    main()
