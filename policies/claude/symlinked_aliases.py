from lunar_policy import Check


def main(node=None):
    c = Check("symlinked-aliases", "CLAUDE.md should exist as a symlink to AGENTS.md", node=node)
    with c:
        instr = c.get_node(".ai.native.claude.instruction_file")
        instr_data = instr.get_value_or_default(".", None)
        if instr_data is None:
            c.skip("No Claude instruction file data collected — enable the claude collector")
            return c

        is_symlink = instr.get_value_or_default(".is_symlink", False)
        if not is_symlink:
            c.fail(
                "CLAUDE.md exists but is not a symlink to AGENTS.md — "
                "replace with: ln -sf AGENTS.md CLAUDE.md"
            )
    return c


if __name__ == "__main__":
    main()
