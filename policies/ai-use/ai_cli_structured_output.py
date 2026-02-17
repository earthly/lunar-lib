from lunar_policy import Check


HEADLESS_INDICATORS = {
    "claude": [" -p ", " --print "],
    "codex": [" exec ", " e "],
    "gemini": [" -p ", " --prompt "],
}

STRUCTURED_OUTPUT_FLAGS = {
    "claude": ["--output-format", "--json-schema"],
    "codex": ["--json", "--experimental-json", "--output-schema"],
    "gemini": ["--output-format"],
}


def is_headless(tool, cmd):
    padded = f" {cmd} "
    for indicator in HEADLESS_INDICATORS.get(tool, []):
        if indicator in padded:
            return True
    return False


def has_structured_output(tool, cmd):
    for flag in STRUCTURED_OUTPUT_FLAGS.get(tool, []):
        if flag in cmd:
            return True
    return False


def main(node=None):
    c = Check("ai-cli-structured-output", "AI CLI tools in CI headless mode should use structured JSON output", node=node)
    with c:
        cmds = c.get_node(".ai_use.cicd.cmds")
        if not cmds.exists():
            c.skip("No AI CLI usage detected in CI")

        for entry in cmds:
            tool = entry.get_value(".tool")
            cmd = entry.get_value(".cmd")

            if not is_headless(tool, cmd):
                continue

            if not has_structured_output(tool, cmd):
                c.fail(
                    f"{tool} headless CI invocation missing structured output flag — "
                    f"JSON output makes automation deterministic and parseable"
                )
    return c


if __name__ == "__main__":
    main()
