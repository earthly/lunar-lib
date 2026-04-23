"""Ensure total code-quality issues are under the configured threshold."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-total", "Total code-quality issues within threshold", node=node)
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

        cq_node = c.get_node(".code_quality")
        if not cq_node.exists():
            c.fail(
                "No code-quality data found. Ensure a code-quality collector like `sonarqube` is configured."
            )
            return c

        total_node = cq_node.get_node(".issues.total")
        if not total_node.exists():
            c.fail(
                "Total issue count not available. Ensure the scanner publishes .code_quality.issues.total."
            )
            return c

        total_value = total_node.get_value()
        c.assert_less_or_equal(
            total_value,
            threshold,
            f"Total code-quality issues ({total_value}) exceeds threshold ({threshold})",
        )
    return c


if __name__ == "__main__":
    main()
