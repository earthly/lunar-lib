from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("canonical-naming", "Root instruction file should use canonical vendor-neutral name", node=node)
    with c:
        instructions = c.get_node(".ai_use.instructions")
        if not instructions.exists():
            c.fail(
                "AI instruction file data not collected — ensure the ai-use collector "
                "is configured and has run for this component"
            )
            return c

        exists = instructions.get_value(".root.exists")

        if not exists:
            return c

        canonical = variable_or_default("canonical_filename", "AGENTS.md")
        actual = instructions.get_value(".root.filename")

        if actual != canonical:
            if actual == "CLAUDE.md":
                c.fail(
                    f"Root instruction file is {actual} — rename to {canonical} and create "
                    f"{actual} as a symlink (Claude Code requires the symlink since it "
                    f"doesn't support {canonical} natively)"
                )
            else:
                c.fail(
                    f"Root instruction file is {actual} — rename to {canonical} "
                    f"(this tool supports {canonical} natively, no symlink needed)"
                )
    return c


if __name__ == "__main__":
    main()
