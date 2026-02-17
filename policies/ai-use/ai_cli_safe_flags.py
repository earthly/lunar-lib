from lunar_policy import Check, variable_or_default


DANGEROUS_FLAGS_BY_TOOL = None


def get_dangerous_flags():
    global DANGEROUS_FLAGS_BY_TOOL
    if DANGEROUS_FLAGS_BY_TOOL is None:
        DANGEROUS_FLAGS_BY_TOOL = {
            "claude": [f.strip() for f in variable_or_default(
                "dangerous_flags_claude",
                "--dangerously-skip-permissions,--allow-dangerously-skip-permissions"
            ).split(",") if f.strip()],
            "codex": [f.strip() for f in variable_or_default(
                "dangerous_flags_codex",
                "--dangerously-bypass-approvals-and-sandbox,--yolo,--full-auto"
            ).split(",") if f.strip()],
            "gemini": [f.strip() for f in variable_or_default(
                "dangerous_flags_gemini",
                "--yolo,-y"
            ).split(",") if f.strip()],
        }
    return DANGEROUS_FLAGS_BY_TOOL


def main(node=None):
    c = Check("ai-cli-safe-flags", "AI CLI tools in CI should not use dangerous permission-bypassing flags", node=node)
    with c:
        cmds = c.get_node(".ai_use.cicd.cmds")
        if not cmds.exists():
            c.skip("No AI CLI usage detected in CI")

        dangerous_flags = get_dangerous_flags()

        for entry in cmds:
            tool = entry.get_value(".tool")
            cmd = entry.get_value(".cmd")
            flags_to_check = dangerous_flags.get(tool, [])

            padded = f" {cmd} "
            for flag in flags_to_check:
                if f" {flag} " in padded or f" {flag}=" in padded:
                    c.fail(f"{tool} CI invocation uses dangerous flag: {flag}")
    return c


if __name__ == "__main__":
    main()
