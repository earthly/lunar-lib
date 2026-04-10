from lunar_policy import Check


def main(node=None):
    c = Check("code-reviewer", "At least one AI code reviewer should be active", node=node)
    with c:
        reviewers = c.get_node(".ai.code_reviewers")
        if not reviewers.exists():
            c.skip("No AI code reviewer data found — enable a tool-specific collector (claude, coderabbit)")
            return c

        found = False
        for entry in reviewers:
            detected = entry.get_value_or_default(".detected", False)
            if detected:
                found = True
                break

        c.assert_true(
            found,
            "No active AI code reviewer detected on this component. "
            "Configure Claude Code Review or CodeRabbit to review pull requests."
        )
    return c


if __name__ == "__main__":
    main()
