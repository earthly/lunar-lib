"""Ensure no high severity vulnerabilities in dependencies (if enabled)."""

from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("no-high", "No high severity vulnerability findings", node=node)
    with c:
        enforce = variable_or_default("enforce_no_high", "true").lower() == "true"
        if not enforce:
            c.skip("High severity check disabled via inputs")
            return c

        c.assert_exists(
            ".sca",
            "No SCA scanning data found. Ensure a scanner (Snyk, Semgrep, etc.) is configured.",
        )

        sca_node = c.get_node(".sca")

        # Check summary first (preferred)
        summary = sca_node.get_node(".summary.has_high")
        if summary.exists():
            c.assert_false(
                summary.get_value(), "High severity vulnerability findings detected"
            )
            return c

        # Fall back to counting
        high = sca_node.get_node(".vulnerabilities.high")
        if high.exists():
            c.assert_equals(
                high.get_value(), 0, "High severity vulnerability findings detected"
            )
            return c

        c.fail("Vulnerability counts not available. Ensure collector reports .sca.vulnerabilities or .sca.summary.")

    return c


if __name__ == "__main__":
    main()
