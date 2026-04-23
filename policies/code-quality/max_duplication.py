"""Ensure duplicated-lines percentage stays under the configured maximum."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("max-duplication", "Duplication stays under maximum threshold", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        threshold_str = variable_or_default("max_duplication_percentage", "5")
        try:
            threshold = float(threshold_str)
        except ValueError:
            raise ValueError(
                f"Policy misconfiguration: 'max_duplication_percentage' must be a number, got '{threshold_str}'"
            )
        if threshold < 0 or threshold > 100:
            raise ValueError(
                f"Policy misconfiguration: 'max_duplication_percentage' must be between 0 and 100, got '{threshold}'"
            )

        cq_node = c.get_node(".code_quality")
        if not cq_node.exists():
            c.fail(
                "No code-quality data found. Ensure a code-quality collector like `sonarqube` is configured."
            )
            return c

        dup_node = cq_node.get_node(".duplication_percentage")
        if not dup_node.exists():
            c.fail(
                "Duplication percentage not reported. Ensure the scanner publishes .code_quality.duplication_percentage."
            )
            return c

        duplication = float(dup_node.get_value())
        c.assert_less_or_equal(
            ".code_quality.duplication_percentage",
            threshold,
            f"Duplication ({duplication}%) exceeds maximum threshold ({threshold}%)",
        )
    return c


if __name__ == "__main__":
    main()
