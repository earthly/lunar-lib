from lunar_policy import Check, variable_or_default


def _check_flags_in_args(args, dangerous_flags):
    """Check flag tokens in a parsed argument list (excludes prompt text)."""
    for arg in args:
        if not isinstance(arg, str) or not arg.startswith("-"):
            continue
        for flag in dangerous_flags:
            if arg == flag or arg.startswith(f"{flag}="):
                return flag
    return None


def main(node=None):
    c = Check("cli-safe-flags", "Codex CLI in CI should not use dangerous permission-bypassing flags", node=node)
    with c:
        cmds_node = c.get_node(".ai.native.codex.cicd.cmds")
        cmds_list = cmds_node.get_value_or_default(".", None)
        if cmds_list is None:
            c.skip("No Codex CLI usage detected in CI")
            return c

        dangerous_str = variable_or_default(
            "dangerous_flags",
            "--dangerously-bypass-approvals-and-sandbox,--yolo,--full-auto"
        )
        dangerous_flags = [f.strip() for f in dangerous_str.split(",") if f.strip()]

        for entry in cmds_node:
            cmd_args = entry.get_value_or_default(".cmd_args", None)
            if cmd_args and isinstance(cmd_args, list):
                found = _check_flags_in_args(cmd_args, dangerous_flags)
                if found:
                    c.fail(f"Codex CI invocation uses dangerous flag: {found}")
            else:
                cmd = entry.get_value_or_default(".cmd", "")
                padded = f" {cmd} "
                for flag in dangerous_flags:
                    if f" {flag} " in padded or f" {flag}=" in padded:
                        c.fail(f"Codex CI invocation uses dangerous flag: {flag}")
    return c


if __name__ == "__main__":
    main()
