"""Ensure no high severity container vulnerabilities (if enabled)."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("no-high", "No high severity container vulnerability findings", node=node)
    with c:
        enforce = variable_or_default("enforce_no_high", "true").lower() == "true"
        if not enforce:
            c.skip("High severity check disabled via inputs")
            return c

        c.assert_exists(
            ".container_scan",
            "No container scanning data found. Ensure a scanner (Trivy, Grype, etc.) is configured.",
        )

        scan_node = c.get_node(".container_scan")

        # Check summary first (preferred)
        summary = scan_node.get_node(".summary.has_high")
        if summary.exists():
            c.assert_false(
                summary.get_value(), "High severity container vulnerability findings detected"
            )
            return c

        # Fall back to counting
        high = scan_node.get_node(".vulnerabilities.high")
        if high.exists():
            c.assert_equals(
                high.get_value(), 0, "High severity container vulnerability findings detected"
            )
            return c

        c.skip("Vulnerability counts not available yet. Collectors need to report .container_scan.vulnerabilities or .container_scan.summary.")

    return c


if __name__ == "__main__":
    main()
