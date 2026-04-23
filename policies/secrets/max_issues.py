"""Ensure secret findings are under a configurable threshold."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-issues", "Secret findings within threshold", node=node)
    with c:
        threshold_str = variable_or_default("max_issues_threshold", "10")
        try:
            threshold = int(threshold_str)
        except ValueError:
            raise ValueError(
                f"Policy misconfiguration: 'max_issues_threshold' must be an integer, got '{threshold_str}'"
            )

        if threshold <= 0:
            raise ValueError(
                f"Policy misconfiguration: 'max_issues_threshold' must be a positive integer, got '{threshold}'"
            )

        secrets_node = c.get_node(".secrets")
        if not secrets_node.exists():
            c.fail("No secret scanning data found. Ensure a scanner (Gitleaks, etc.) is configured.")
            return c

        issues_node = secrets_node.get_node(".issues")
        if not issues_node.exists():
            c.fail("Issues data not available. Ensure collector reports .secrets.issues.")
            return c

        issue_count = len(issues_node.get_value())
        c.assert_less_or_equal(
            issue_count,
            threshold,
            f"Secret findings ({issue_count}) exceeds threshold ({threshold})",
        )
    return c


if __name__ == "__main__":
    main()
