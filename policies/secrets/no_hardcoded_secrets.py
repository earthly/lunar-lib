"""Ensure no hardcoded secrets are detected in the codebase."""

from lunar_policy import Check


def main(node=None):
    c = Check("no-hardcoded-secrets", "No hardcoded secrets detected", node=node)
    with c:
        secrets_node = c.get_node(".secrets")
        if not secrets_node.exists():
            c.fail("No secret scanning data found. Ensure a scanner (Gitleaks, etc.) is configured.")
            return c

        issues_node = secrets_node.get_node(".issues")
        if not issues_node.exists():
            c.skip("No issues data available yet")
            return c

        issues = issues_node.get_value()
        c.assert_true(
            len(issues) == 0,
            f"Hardcoded secrets detected: {len(issues)} finding(s) in source code",
        )
    return c


if __name__ == "__main__":
    main()
