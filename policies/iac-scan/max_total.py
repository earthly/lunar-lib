"""Ensure total infrastructure security findings under threshold."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-total", "Total infrastructure security findings within threshold", node=node)
    with c:
        threshold_str = variable_or_default("max_total_threshold", "0")
        try:
            threshold = int(threshold_str)
        except ValueError:
            raise ValueError(
                f"Policy misconfiguration: 'max_total_threshold' must be an integer, got '{threshold_str}'"
            )

        if threshold < 0:
            raise ValueError(
                f"Policy misconfiguration: 'max_total_threshold' must be non-negative, got '{threshold}'"
            )

        if threshold == 0:
            c.skip("No maximum threshold configured (set max_total_threshold > 0 to enable)")
            return c

        scan_node = c.get_node(".iac_scan")
        if not scan_node.exists():
            c.fail("No IaC scanning data found. Ensure a scanner (Trivy, Checkov, etc.) is configured.")
            return c
        total_node = scan_node.get_node(".findings.total")
        if not total_node.exists():
            c.skip("Total findings count not available yet. Collectors need to report .iac_scan.findings.total.")
            return c

        total_value = total_node.get_value()
        c.assert_less_or_equal(
            total_value,
            threshold,
            f"Total infrastructure security findings ({total_value}) exceeds threshold ({threshold})",
        )
    return c


if __name__ == "__main__":
    main()
