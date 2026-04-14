from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("canonical-naming", "Root instruction file should use canonical vendor-neutral name", node=node)
    with c:
        instructions = c.get_node(".ai.instructions")
        if not instructions.exists():
            c.skip("No instruction file data collected — enable the ai collector")
            return c

        canonical = variable_or_default("canonical_filename", "AGENTS.md")

        root_exists = instructions.get_value_or_default(".root.exists", False)
        if root_exists:
            actual = instructions.get_value_or_default(".root.filename", "")
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

        # Root not found — check tool-specific files in all[]
        all_files = instructions.get_value_or_default(".all", [])
        if not all_files:
            c.fail("No agent instruction file found at repository root")
            return c

        # Tool-specific files exist but no canonical AGENTS.md
        names = [f.get("filename", "") for f in all_files if isinstance(f, dict)]
        if "CLAUDE.md" in names:
            c.fail(
                f"Found CLAUDE.md but no {canonical} — rename to {canonical} and create "
                f"CLAUDE.md as a symlink (Claude Code requires the symlink since it "
                f"doesn't support {canonical} natively)"
            )
        else:
            found = ", ".join(names[:3]) or "tool-specific files"
            c.fail(
                f"Found {found} but no {canonical} — create {canonical} as the "
                f"vendor-neutral root instruction file"
            )
    return c


if __name__ == "__main__":
    main()
