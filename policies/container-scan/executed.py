"""Verify container image scanning was executed."""

from lunar_policy import Check


def main(node=None):
    c = Check("executed", "Container scan must be executed", node=node)
    with c:
        if not c.get_node(".containers").exists():
            c.skip("No container definitions detected in this component")

        c.assert_exists(
            ".container_scan",
            "No container scanning data found. Ensure a scanner (Trivy, Grype, etc.) is configured.",
        )
    return c


if __name__ == "__main__":
    main()
