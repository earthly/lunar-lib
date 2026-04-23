"""Ensure no code-quality issues at or above the configured severity threshold."""

from lunar_policy import Check, variable_or_default

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def main(node=None):
    c = Check("max-severity", "No issues at or above severity threshold", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        min_severity = variable_or_default("min_severity", "high").lower()
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        cq_node = c.get_node(".code_quality")
        if not cq_node.exists():
            c.fail(
                "No code-quality data found. Ensure a code-quality collector like `sonarqube` is configured."
            )
            return c

        issues_node = cq_node.get_node(".issues")
        if not issues_node.exists():
            c.fail(
                "Issue counts not available. Ensure the scanner publishes .code_quality.issues."
            )
            return c

        severity_index = SEVERITY_ORDER.index(min_severity)
        severities_to_check = SEVERITY_ORDER[: severity_index + 1]

        for severity in severities_to_check:
            count_node = issues_node.get_node(f".{severity}")
            if count_node.exists():
                count = count_node.get_value()
                if count > 0:
                    c.fail(
                        f"{severity.capitalize()} code-quality issues detected ({count} found)"
                    )
                    return c
    return c


if __name__ == "__main__":
    main()
