from lunar_policy import Check, variable_or_default

MAX_NAMED = 5


def _num(entry, key):
    value = entry.get(key, 0)
    return value if isinstance(value, (int, float)) else 0


def _over(files, key, limit):
    return sorted((f for f in files if _num(f, key) > limit), key=lambda f: _num(f, key), reverse=True)


def _name(entry):
    return entry.get("path") or entry.get("filename") or "(unnamed)"


def _describe(over, key, unit):
    shown = ", ".join(f"{_name(f)} ({_num(f, key)} {unit})" for f in over[:MAX_NAMED])
    if len(over) > MAX_NAMED:
        shown += f", +{len(over) - MAX_NAMED} more"
    return shown


def main(node=None):
    c = Check("instruction-file-length", "Instruction files should be within reasonable length bounds", node=node)
    with c:
        instructions = c.get_node(".ai.instructions")
        if not instructions.exists():
            c.fail(
                "No instruction file data found — ensure the ai collector is enabled. "
                "Exclude this policy if instruction files are not required for this component."
            )
            return c

        exists = instructions.get_value_or_default(".root.exists", False)
        if not exists:
            c.fail("No agent instruction file found at repository root")
            return c

        min_lines = int(variable_or_default("min_lines", "10"))
        max_lines = int(variable_or_default("max_lines", "300"))
        max_bytes = int(variable_or_default("max_bytes", "32768"))
        max_total_bytes = int(variable_or_default("max_total_bytes", "32768"))

        root_lines = instructions.get_value_or_default(".root.lines", 0)

        if min_lines > 0:
            c.assert_greater_or_equal(
                root_lines, min_lines,
                f"Root instruction file has {root_lines} lines — too short to be useful. "
                f"Add project overview, build commands, and architecture notes."
            )

        # The caps below apply to every instruction file, not just the root one.
        # `total_bytes` only sums the AGENTS.md files the ai collector found, so a
        # CLAUDE.md the claude collector appended to all[] is invisible to it.
        all_files = instructions.get_value_or_default(".all", []) or []
        files = [f for f in all_files if isinstance(f, dict) and not f.get("is_symlink", False)]
        if not files:
            files = [{
                "filename": instructions.get_value_or_default(".root.filename", "AGENTS.md"),
                "lines": root_lines,
                "bytes": instructions.get_value_or_default(".root.bytes", 0),
            }]

        if max_lines > 0:
            over = _over(files, "lines", max_lines)
            c.assert_less_or_equal(
                max((_num(f, "lines") for f in files), default=0), max_lines,
                f"Instruction files over the {max_lines}-line cap: {_describe(over, 'lines', 'lines')}. "
                f"Too long wastes context window budget. Use progressive disclosure: split into "
                f"subdirectory files and link to external docs."
            )

        if max_bytes > 0:
            over = _over(files, "bytes", max_bytes)
            c.assert_less_or_equal(
                max((_num(f, "bytes") for f in files), default=0), max_bytes,
                f"Instruction files over the {max_bytes}-byte cap: {_describe(over, 'bytes', 'bytes')}. "
                f"Reduce content or split it across subdirectory files."
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
