#!/bin/sh
# ruff-format.sh — agent-after-file-edit check for the python.ruff-format sub-probe.
#
# Reads the framework PostToolUse JSON payload on stdin, extracts the
# edited file path (.tool_input.file_path — Claude, Cursor, Codex, and
# Gemini all normalise to this key per lunar-probe's adapter layer),
# and runs `ruff format --check` against it. Exit non-zero on formatting
# drift so the probe fires and the agent sees Ruff's diagnostic via
# `{check_stdout}` in the manifest's `message:` template. stderr is
# folded into stdout so parse/config errors surface there too.
#
# `--check` is read-only: it reports whether the file WOULD be
# reformatted and never rewrites it. The agent owns the actual fix
# (`ruff format {file}`). Per PROBE-PLAYBOOK-AI, `check:` is never
# allowed to mutate the working tree.
#
# `ruff` presence is owned by the manifest's `requires:` block, which
# surfaces a missing linter once at session-end rather than skipping
# silently. The `command -v ruff` guard below is defense-in-depth for
# standalone invocation (e.g. running this script outside lunar-probe).
#
# Skip-safe (exit 0, edit proceeds) when:
#   - jq isn't on PATH (can't parse the payload).
#   - ruff isn't on PATH (standalone safety net; requires: handles the agent flow).
#   - The payload has no file_path.
#   - The file doesn't exist on disk (mid-edit race, deleted file).
#
# POSIX sh only — no bash arrays / [[ ]] / pipefail. Runs cleanly under
# dash and BusyBox sh per PROBE-PLAYBOOK-AI § "Common pitfalls".

set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v ruff >/dev/null 2>&1 || exit 0

FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

ruff format --check -- "$FILE" 2>&1
