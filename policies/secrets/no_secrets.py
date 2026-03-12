"""Ensure no hardcoded secrets are detected in the codebase."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-secrets", "No hardcoded secrets in code", node=node)
    with c:
        secrets_node = c.get_node(".secrets")
        if not secrets_node.exists():
            c.fail(
                "No secret scanning data found. Ensure a scanner (Gitleaks, TruffleHog, etc.) is configured."
            )
            return c

        # Check .secrets.clean first (preferred)
        clean_node = secrets_node.get_node(".clean")
        if clean_node.exists():
            clean = clean_node.get_value()
            c.assert_true(
                clean,
                "Hardcoded secrets detected in code. Review .secrets.issues for details.",
            )
            return c

        # Fall back to findings count
        total_node = secrets_node.get_node(".findings.total")
        if total_node.exists():
            total = total_node.get_value()
            c.assert_equals(
                total,
                0,
                f"Hardcoded secrets detected ({total} found). Review .secrets.issues for details.",
            )
            return c

        # Scan data exists but no findings/clean field — collector bug
        raise ValueError(
            "Secret scan data exists but findings not available. "
            "Ensure collector reports .secrets.clean or .secrets.findings.total."
        )

    return c


if __name__ == "__main__":
    main()
