"""Ensure total container vulnerabilities under threshold."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-total", "Total container vulnerability findings within threshold", node=node)
    with c:
        threshold_str = variable_or_default("max_total_threshold", "0")
        try:
            threshold = int(threshold_str)
        except ValueError:
            raise ValueError(
                f"Policy misconfiguration: 'max_total_threshold' must be an integer, got '{threshold_str}'"
            )

        if threshold <= 0:
            raise ValueError(
                f"Policy misconfiguration: 'max_total_threshold' must be a positive integer, got '{threshold}'"
            )

        if not c.get_node(".containers").exists():
            c.skip("No container definitions detected in this component")

        scan_node = c.get_node(".container_scan")
        if not scan_node.exists():
            c.fail("No container scanning data found. Ensure a scanner (Trivy, Grype, etc.) is configured.")
            return c
        total_node = scan_node.get_node(".vulnerabilities.total")
        if not total_node.exists():
            c.fail("Total findings count not available. Ensure collector reports .container_scan.vulnerabilities.total.")
            return c

        total_value = total_node.get_value()
        c.assert_less_or_equal(
            total_value,
            threshold,
            f"Total container vulnerability findings ({total_value}) exceeds threshold ({threshold})",
        )
    return c


if __name__ == "__main__":
    main()
