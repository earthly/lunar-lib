from lunar_policy import Check


def main(node=None):
    c = Check("code-reviewer", "At least one AI code reviewer should be active", node=node)
    with c:
        reviewers_node = c.get_node(".ai.code_reviewers")
        reviewers_list = reviewers_node.get_value_or_default(".", None)
        if reviewers_list is None:
            c.fail(
                "No AI code reviewer data found — enable a tool-specific collector "
                "(claude, coderabbit). Exclude this policy if code review is not "
                "required for this component."
            )
            return c

        found = False
        for entry in reviewers_node:
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
