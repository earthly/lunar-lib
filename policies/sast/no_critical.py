"""Ensure no critical severity code findings."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-critical", "No critical code findings", node=node)
    with c:
        sast_node = c.get_node(".sast")
        if not sast_node.exists():
            c.fail("No SAST scanning data found. Ensure a scanner (Semgrep, CodeQL, etc.) is configured.")
            return c

        # Check summary first (preferred)
        summary = sast_node.get_node(".summary.has_critical")
        if summary.exists():
            c.assert_false(summary.get_value(), "Critical code findings detected")
            return c

        # Fall back to counting
        critical = sast_node.get_node(".findings.critical")
        if critical.exists():
            c.assert_equals(critical.get_value(), 0, "Critical code findings detected")
            return c

        c.skip("Finding counts not available yet. Collectors need to report .sast.findings or .sast.summary.")

    return c


if __name__ == "__main__":
    main()
