"""Ensure no critical severity infrastructure security findings."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-critical", "No critical infrastructure security findings", node=node)
    with c:
        # Skip if no scan data (don't fail components without this scanner type)
        scan_node = c.get_node(".iac_scan")
        if not scan_node.exists():
            c.skip("No IaC scan data available")
            return c

        # Check summary first (preferred)
        summary = scan_node.get_node(".summary.has_critical")
        if summary.exists():
            c.assert_false(
                summary.get_value(), "Critical infrastructure security findings detected"
            )
            return c

        # Fall back to counting
        critical = scan_node.get_node(".findings.critical")
        if critical.exists():
            c.assert_equals(
                critical.get_value(), 0, "Critical infrastructure security findings detected"
            )

    return c


if __name__ == "__main__":
    main()
