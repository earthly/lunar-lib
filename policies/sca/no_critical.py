"""Ensure no critical severity vulnerabilities in dependencies."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-critical", "No critical vulnerability findings", node=node)
    with c:
        sca_node = c.get_node(".sca")
        if not sca_node.exists():
            c.fail("No SCA scanning data found. Ensure a scanner (Snyk, Semgrep, etc.) is configured.")
            return c

        # Check summary first (preferred)
        summary = sca_node.get_node(".summary.has_critical")
        if summary.exists():
            c.assert_false(
                summary.get_value(), "Critical vulnerability findings detected"
            )
            return c

        # Fall back to counting
        critical = sca_node.get_node(".vulnerabilities.critical")
        if critical.exists():
            c.assert_equals(
                critical.get_value(), 0, "Critical vulnerability findings detected"
            )
            return c

        c.skip("Vulnerability counts not available yet. Collectors need to report .sca.vulnerabilities or .sca.summary.")

    return c


if __name__ == "__main__":
    main()
