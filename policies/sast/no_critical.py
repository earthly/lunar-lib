"""Ensure no critical severity code findings."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-critical", "No critical code findings", node=node)
    with c:
        # Skip if no scan data (don't fail components without this scanner type)
        sast_node = c.get_node(".sast")
        if not sast_node.exists():
            c.skip("No SAST data available")
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


if __name__ == "__main__":
    main()
