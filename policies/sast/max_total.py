"""Ensure total code findings under threshold."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-total", "Total code findings within threshold", node=node)
    with c:
        threshold_str = variable_or_default("max_total_threshold", "0")
        threshold = int(threshold_str)

        if threshold == 0:
            c.skip("No maximum threshold configured (set max_total_threshold > 0 to enable)")
            return c

        sast_node = c.get_node(".sast")
        if not sast_node.exists():
            c.skip("No SAST data available")
            return c

        total_node = sast_node.get_node(".findings.total")
        if not total_node.exists():
            c.skip("Total findings count not available")
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
