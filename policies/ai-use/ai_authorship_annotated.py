from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("ai-authorship-annotated", "Commits should include AI authorship annotations", node=node)
    with c:
        authorship = c.get_node(".ai_use.authorship")
        if not authorship.exists():
            c.fail(
                "AI authorship data not collected — ensure the ai-use collector "
                "is configured and has run for this component"
            )
            return c

        total = authorship.get_value(".total_commits")

        if total == 0:
            return c

        annotated = authorship.get_value(".annotated_commits")
        min_pct = int(variable_or_default("min_annotation_percentage", "0"))

        actual_pct = (annotated / total) * 100

        if min_pct == 0:
            return c

        c.assert_greater_or_equal(
            actual_pct, min_pct,
            f"{annotated}/{total} commits ({actual_pct:.0f}%) have AI annotations, "
            f"need {min_pct}%. Install git-ai (usegitai.com) for automated tracking, "
            f"or add git trailers manually (e.g. AI-model: claude-4)."
        )
    return c


if __name__ == "__main__":
    main()
