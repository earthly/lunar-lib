"""Ensure no high severity infrastructure security findings (if enabled)."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("no-high", "No high severity infrastructure security findings", node=node)
    with c:
        enforce = variable_or_default("enforce_no_high", "true").lower() == "true"
        if not enforce:
            c.skip("High severity check disabled via inputs")
            return c

        scan_node = c.get_node(".iac_scan")
        if not scan_node.exists():
            c.skip("No IaC scan data available")
            return c

        # Check summary first (preferred)
        summary = scan_node.get_node(".summary.has_high")
        if summary.exists():
            c.assert_false(
                summary.get_value(), "High severity infrastructure security findings detected"
            )
            return c

        # Fall back to counting
        high = scan_node.get_node(".findings.high")
        if high.exists():
            c.assert_equals(
                high.get_value(), 0, "High severity infrastructure security findings detected"
            )

    return c


if __name__ == "__main__":
    main()
