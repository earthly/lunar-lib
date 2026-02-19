from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("instruction-file-length", "Root instruction file should be within reasonable length bounds", node=node)
    with c:
        instructions = c.get_node(".ai_use.instructions")
        if not instructions.exists():
            c.fail(
                "AI instruction file data not collected — ensure the ai-use collector "
                "is configured and has run for this component"
            )
            return c

        exists = instructions.get_value(".root.exists")

        min_lines = int(variable_or_default("min_lines", "10"))
        max_lines = int(variable_or_default("max_lines", "300"))
        max_total_bytes = int(variable_or_default("max_total_bytes", "32768"))

        lines = instructions.get_value_or_default(".root.lines", 0) if exists else 0

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
            total_bytes = instructions.get_value_or_default(".total_bytes", 0)
            c.assert_less_or_equal(
                total_bytes, max_total_bytes,
                f"Combined instruction files are {total_bytes} bytes "
                f"(max {max_total_bytes}). Reduce content or split across fewer files."
            )
    return c


if __name__ == "__main__":
    main()
