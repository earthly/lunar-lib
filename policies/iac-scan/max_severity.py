"""Ensure no findings at or above the configured severity threshold."""

from lunar_policy import Check, variable_or_default

SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def main(node=None):
    c = Check("max-severity", "No findings at or above severity threshold", node=node)
    with c:
        if not c.get_node(".iac").exists():
            c.skip("No infrastructure as code detected in this component")

        min_severity = variable_or_default("min_severity", "high").lower()
        
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Policy misconfiguration: 'min_severity' must be one of {SEVERITY_ORDER}, got '{min_severity}'"
            )

        c.assert_exists(
            ".iac_scan",
            "No IaC scan data found. Ensure a scanner (Checkov, tfsec, etc.) is configured.",
        )

        scan_node = c.get_node(".iac_scan")
        
        # Get the index of min_severity to know which severities to check
        severity_index = SEVERITY_ORDER.index(min_severity)
        severities_to_check = SEVERITY_ORDER[:severity_index + 1]

        # Check summary booleans first (preferred)
        for severity in severities_to_check:
            summary_key = f".summary.has_{severity}"
            summary = scan_node.get_node(summary_key)
            if summary.exists() and summary.get_value():
                c.fail(f"{severity.capitalize()} IaC misconfigurations detected")
                return c

        # Fall back to counting
        for severity in severities_to_check:
            count_key = f".findings.{severity}"
            count_node = scan_node.get_node(count_key)
            if count_node.exists():
                count = count_node.get_value()
                if count > 0:
                    c.fail(f"{severity.capitalize()} IaC misconfigurations detected ({count} found)")
                    return c

        # If we get here with no data found, fail
        has_any_data = False
        for severity in severities_to_check:
            if scan_node.get_node(f".summary.has_{severity}").exists():
                has_any_data = True
                break
            if scan_node.get_node(f".findings.{severity}").exists():
                has_any_data = True
                break
        
        if not has_any_data:
            raise ValueError(
                "Finding counts not available. Ensure collector reports .iac_scan.findings or .iac_scan.summary."
            )

    return c


if __name__ == "__main__":
    main()
