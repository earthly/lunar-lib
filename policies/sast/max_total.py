"""Ensure total code findings under threshold."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-total", "Total code findings within threshold", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

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

        sast_node = c.get_node(".sast")
        if not sast_node.exists():
            c.fail("No SAST scanning data found. Ensure a scanner (Semgrep, CodeQL, etc.) is configured.")
            return c
        total_node = sast_node.get_node(".findings.total")
        if not total_node.exists():
            c.fail("Total findings count not available. Ensure collector reports .sast.findings.total.")
            return c

        total_value = total_node.get_value()
        c.assert_less_or_equal(
            total_value,
            threshold,
            f"Total code findings ({total_value}) exceeds threshold ({threshold})",
        )
    return c


if __name__ == "__main__":
    main()
