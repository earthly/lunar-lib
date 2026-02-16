"""Ensure no high severity code findings (if enabled)."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("no-high", "No high severity code findings", node=node)
    with c:
        enforce = variable_or_default("enforce_no_high", "true").lower() == "true"
        if not enforce:
            c.skip("High severity check disabled via inputs")
            return c

        sast_node = c.get_node(".sast")
        if not sast_node.exists():
            c.fail("No SAST scanning data found. Ensure a scanner (Semgrep, CodeQL, etc.) is configured.")
            return c

        # Check summary first (preferred)
        summary = sast_node.get_node(".summary.has_high")
        if summary.exists():
            c.assert_false(summary.get_value(), "High severity code findings detected")
            return c

        # Fall back to counting
        high = sast_node.get_node(".findings.high")
        if high.exists():
            c.assert_equals(high.get_value(), 0, "High severity code findings detected")
            return c

        c.skip("Finding counts not available yet. Collectors need to report .sast.findings or .sast.summary.")

    return c


if __name__ == "__main__":
    main()
