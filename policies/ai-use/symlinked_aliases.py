from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("symlinked-aliases", "CLAUDE.md symlinks should exist alongside AGENTS.md files", node=node)
    with c:
        exists = c.get_value(".ai_use.instructions.root.exists")

        if not exists:
            return c

        canonical = variable_or_default("canonical_filename", "AGENTS.md")
        required_str = variable_or_default("required_symlinks", "CLAUDE.md")
        required_symlinks = [s.strip() for s in required_str.split(",") if s.strip()]

        if not required_symlinks:
            return c

        directories = c.get_node(".ai_use.instructions.directories")
        if not directories.exists():
            return c

        for directory in directories:
            dir_path = directory.get_value(".dir")
            files_node = directory.get_node(".files")
            if not files_node.exists():
                continue

            filenames = {}
            for f in files_node:
                name = f.get_value(".filename")
                is_symlink = f.get_value_or_default(".is_symlink", False)
                filenames[name] = is_symlink

            if canonical not in filenames:
                continue

            if filenames[canonical]:
                c.fail(
                    f"{dir_path}: {canonical} is a symlink — it should be the real file, "
                    f"not a symlink"
                )
                continue

            for symlink in required_symlinks:
                if symlink not in filenames:
                    c.fail(
                        f"{dir_path}: missing {symlink} symlink — run: "
                        f"ln -s {canonical} {symlink}"
                    )
                elif not filenames[symlink]:
                    c.fail(
                        f"{dir_path}: {symlink} exists but is not a symlink to {canonical} — "
                        f"replace with: ln -sf {canonical} {symlink}"
                    )
    return c


if __name__ == "__main__":
    main()
