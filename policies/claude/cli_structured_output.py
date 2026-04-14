from lunar_policy import Check


HEADLESS_INDICATORS = [" -p ", " --print "]
STRUCTURED_FLAGS = ["--output-format", "--json-schema"]


def main(node=None):
    c = Check("cli-structured-output", "Claude CLI in CI headless mode should use structured JSON output", node=node)
    with c:
        cmds = c.get_node(".ai.native.claude.cicd.cmds")
        if not cmds.exists():
            c.skip("No Claude CLI usage detected in CI")
            return c

        for entry in cmds:
            cmd = entry.get_value_or_default(".cmd", "")
            padded = f" {cmd} "

            is_headless = any(ind in padded for ind in HEADLESS_INDICATORS)
            if not is_headless:
                continue

            has_structured = any(flag in cmd for flag in STRUCTURED_FLAGS)
            if not has_structured:
                c.fail(
                    "Claude headless CI invocation missing structured output flag — "
                    "JSON output makes automation deterministic and parseable"
                )
    return c


if __name__ == "__main__":
    main()
