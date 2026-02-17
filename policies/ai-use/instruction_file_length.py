from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("instruction-file-length", "Root instruction file should be within reasonable length bounds", node=node)
    with c:
        exists = c.get_value(".ai_use.instructions.root.exists")

        min_lines = int(variable_or_default("min_lines", "10"))
        max_lines = int(variable_or_default("max_lines", "300"))
        max_total_bytes = int(variable_or_default("max_total_bytes", "32768"))

        lines = c.get_value_or_default(".ai_use.instructions.root.lines", 0) if exists else 0

        if min_lines > 0:
            c.assert_greater_or_equal(
                lines, min_lines,
                f"Root instruction file has {lines} lines — too short to be useful. "
                f"Add project overview, build commands, and architecture notes."
            )

        if max_lines > 0:
            c.assert_less_or_equal(
                lines, max_lines,
                f"Root instruction file has {lines} lines — too long, wastes context window budget. "
                f"Use progressive disclosure: split into subdirectory files and link to external docs."
            )

        if max_total_bytes > 0:
            total_bytes = c.get_value_or_default(".ai_use.instructions.total_bytes", 0)
            c.assert_less_or_equal(
                total_bytes, max_total_bytes,
                f"Combined instruction files are {total_bytes} bytes "
                f"(max {max_total_bytes}). Reduce content or split across fewer files."
            )
    return c


if __name__ == "__main__":
    main()
