from lunar_policy import Check


def main(node=None):
    c = Check("instruction-file-exists", "Agent instruction file should exist at repo root", node=node)
    with c:
        exists = c.get_value(".ai_use.instructions.root.exists")
        c.assert_true(
            exists,
            "No agent instruction file found at repository root "
            "(e.g. AGENTS.md, CLAUDE.md, GEMINI.md)"
        )
    return c


if __name__ == "__main__":
    main()
