from lunar_policy import Check, variable_or_default


def main(node=None):
    c = Check("cli-safe-flags", "Codex CLI in CI should not use dangerous permission-bypassing flags", node=node)
    with c:
        cmds = c.get_node(".ai.native.codex.cicd.cmds")
        if not cmds.exists():
            c.skip("No Codex CLI usage detected in CI")
            return c

        dangerous_str = variable_or_default("dangerous_flags", "--full-auto")
        dangerous_flags = [f.strip() for f in dangerous_str.split(",") if f.strip()]

        for entry in cmds:
            cmd = entry.get_value(".cmd")
            padded = f" {cmd} "
            for flag in dangerous_flags:
                if f" {flag} " in padded or f" {flag}=" in padded:
                    c.fail(f"Codex CI invocation uses dangerous flag: {flag}")
    return c


if __name__ == "__main__":
    main()
