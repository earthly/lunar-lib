from lunar_policy import Check


HEADLESS_INDICATORS = [" exec ", " e "]
STRUCTURED_FLAGS = ["--json", "--experimental-json", "--output-schema"]


def main(node=None):
    c = Check("cli-structured-output", "Codex CLI in CI should use structured JSON output", node=node)
    with c:
        cmds = c.get_node(".ai.native.codex.cicd.cmds")
        if not cmds.exists():
            c.skip("No Codex CLI usage detected in CI")
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
                    "Codex headless CI invocation missing structured output flag — "
                    "JSON output makes automation deterministic and parseable"
                )
    return c


if __name__ == "__main__":
    main()
