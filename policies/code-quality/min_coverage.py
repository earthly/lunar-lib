"""Ensure line-coverage percentage meets the configured minimum."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("min-coverage", "Line coverage meets minimum threshold", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        threshold_str = variable_or_default("min_coverage_percentage", "80")
        try:
            threshold = float(threshold_str)
        except ValueError:
            raise ValueError(
                f"Policy misconfiguration: 'min_coverage_percentage' must be a number, got '{threshold_str}'"
            )
        if threshold < 0 or threshold > 100:
            raise ValueError(
                f"Policy misconfiguration: 'min_coverage_percentage' must be between 0 and 100, got '{threshold}'"
            )

        cq_node = c.get_node(".code_quality")
        if not cq_node.exists():
            c.fail(
                "No code-quality data found. Ensure a code-quality collector like `sonarqube` is configured."
            )
            return c

        coverage_node = cq_node.get_node(".coverage_percentage")
        if not coverage_node.exists():
            c.fail(
                "Line coverage not reported. Ensure the scanner publishes .code_quality.coverage_percentage."
            )
            return c

        coverage = float(coverage_node.get_value())
        c.assert_greater_or_equal(
            ".code_quality.coverage_percentage",
            threshold,
            f"Line coverage ({coverage}%) below minimum threshold ({threshold}%)",
        )
    return c


if __name__ == "__main__":
    main()
