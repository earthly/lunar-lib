"""Ensure no critical severity container vulnerabilities."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-critical", "No critical container vulnerability findings", node=node)
    with c:
        c.assert_exists(
            ".container_scan",
            "No container scanning data found. Ensure a scanner (Trivy, Grype, etc.) is configured.",
        )

        scan_node = c.get_node(".container_scan")

        # Check summary first (preferred)
        summary = scan_node.get_node(".summary.has_critical")
        if summary.exists():
            c.assert_false(
                summary.get_value(), "Critical container vulnerability findings detected"
            )
            return c

        # Fall back to counting
        critical = scan_node.get_node(".vulnerabilities.critical")
        if critical.exists():
            c.assert_equals(
                critical.get_value(), 0, "Critical container vulnerability findings detected"
            )
            return c

        c.skip("Vulnerability counts not available yet. Collectors need to report .container_scan.vulnerabilities or .container_scan.summary.")

    return c


if __name__ == "__main__":
    main()
