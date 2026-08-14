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

        # One failure per finding so each secret is reported with its location.
        for issue in issues_node:
            file = issue.get_value_or_default(".file", None)
            line = issue.get_value_or_default(".line", None)
            rule = issue.get_value_or_default(".rule", None)
            description = issue.get_value_or_default(".secret_type", None)

            location = file or "<unknown file>"
            if line is not None:
                location = f"{location}:{line}"

            message = f"Hardcoded secret detected at {location}"
            if rule:
                message += f" ({rule})"
            if description:
                message += f": {description}"
            c.fail(message)
    return c


if __name__ == "__main__":
    main()
