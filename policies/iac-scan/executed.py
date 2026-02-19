"""Verify IaC scanning was executed."""

from lunar_policy import Check


def main(node=None):
    c = Check("executed", "IaC scan must be executed", node=node)
    with c:
        if not c.get_node(".iac").exists():
            c.skip("No infrastructure as code detected in this component")

        c.assert_exists(
            ".iac_scan",
            "No IaC scanning data found. Ensure a scanner (Trivy, Checkov, etc.) is configured.",
        )
    return c


if __name__ == "__main__":
    main()
