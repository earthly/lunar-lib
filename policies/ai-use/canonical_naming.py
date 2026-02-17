from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("canonical-naming", "Root instruction file should use canonical vendor-neutral name", node=node)
    with c:
        exists = c.get_value(".ai_use.instructions.root.exists")

        if not exists:
            return c

        canonical = variable_or_default("canonical_filename", "AGENTS.md")
        actual = c.get_value(".ai_use.instructions.root.filename")

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
