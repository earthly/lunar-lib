from lunar_policy import Check


def main(node=None):
    c = Check("instruction-file-exists", "Agent instruction file should exist at repo root", node=node)
    with c:
        instructions = c.get_node(".ai.instructions")
        instr_data = instructions.get_value_or_default(".", None)
        if instr_data is None:
            c.fail(
                "No instruction file data found — ensure the ai collector is enabled. "
                "Exclude this policy if instruction files are not required for this component."
            )
            return c

        root_exists = instructions.get_value_or_default(".root.exists", False)
        all_files = instructions.get_value_or_default(".all", [])

        if root_exists or all_files:
            return c

        c.fail(
            "No agent instruction file found at repository root "
            "(e.g. AGENTS.md, CLAUDE.md, GEMINI.md)"
        )
    return c


if __name__ == "__main__":
    main()
