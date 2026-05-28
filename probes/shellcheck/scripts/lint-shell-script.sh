#!/bin/sh
# lint-shell-script.sh — agent-after-file-edit check for the shellcheck probe.
#
# Reads the framework PostToolUse JSON payload on stdin, extracts the
# edited file path (.tool_input.file_path — Claude, Cursor, Codex, and
# Gemini all normalise to this key per lunar-probe's adapter layer),
# and runs `shellcheck` against it. Exit non-zero on findings so the
# probe fires and the agent sees ShellCheck's diagnostic via
# `{check_stdout}` in the manifest's `message:` template.
#
# Skip-safe (exit 0, edit proceeds) when:
#   - jq isn't on PATH (can't parse payload).
#   - shellcheck isn't on PATH (repos without it never see this fire).
#   - The payload has no file_path.
#   - The file doesn't exist on disk (mid-edit race, deleted file).
#
# POSIX sh only — no bash arrays / [[ ]] / pipefail. Runs cleanly under
# dash and BusyBox sh per PROBE-PLAYBOOK-AI § "Common pitfalls".

set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v shellcheck >/dev/null 2>&1 || exit 0

FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

shellcheck -- "$FILE"
