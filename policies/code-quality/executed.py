"""Verify a code-quality scanner was executed on the component."""

from lunar_policy import Check


def main(node=None):
    c = Check("executed", "Code-quality scan must be executed", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        c.assert_exists(
            ".code_quality",
            "No code-quality data found. Ensure a code-quality collector like `sonarqube` is configured.",
        )
    return c


if __name__ == "__main__":
    main()
