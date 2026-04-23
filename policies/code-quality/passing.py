"""Verify the code-quality scanner's overall pass/fail signal is green."""

from lunar_policy import Check


def main(node=None):
    c = Check("passing", "Code-quality scan must be passing", node=node)
    with c:
        if not c.get_node(".lang").exists():
            c.skip("No programming language detected in this component")

        cq_node = c.get_node(".code_quality")
        if not cq_node.exists():
            c.fail(
                "No code-quality data found. Ensure a code-quality collector like `sonarqube` is configured."
            )
            return c

        passing_node = cq_node.get_node(".passing")
        if not passing_node.exists():
            c.fail(
                "Code-quality pass/fail signal not available. Ensure collector reports .code_quality.passing."
            )
            return c

        c.assert_equals(
            ".code_quality.passing",
            True,
            "Code-quality scan is failing — scanner reported quality gate as not passing.",
        )
    return c


if __name__ == "__main__":
    main()
