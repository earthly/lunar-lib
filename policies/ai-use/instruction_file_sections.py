from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("instruction-file-sections", "Root instruction file should contain required sections", node=node)
    with c:
        exists = c.get_value(".ai_use.instructions.root.exists")

        required_str = variable_or_default("required_sections", "Project Overview,Build Commands")
        if not required_str:
            raise ValueError(
                "Policy misconfiguration: 'required_sections' is empty. "
                "Configure required sections or exclude this check."
            )

        required = [s.strip() for s in required_str.split(",") if s.strip()]
        if not required:
            raise ValueError(
                "Policy misconfiguration: 'required_sections' has no valid entries. "
                "Configure required sections or exclude this check."
            )

        if not exists:
            c.fail(
                f"No instruction file at root — missing required sections: {', '.join(required)}"
            )
            return c

        sections = c.get_value_or_default(".ai_use.instructions.root.sections", [])
        sections_lower = [s.lower() for s in sections]

        missing = [r for r in required if r.lower() not in sections_lower]

        if missing:
            c.fail(
                f"Root instruction file is missing required sections: {', '.join(missing)}"
            )
    return c


if __name__ == "__main__":
    main()
