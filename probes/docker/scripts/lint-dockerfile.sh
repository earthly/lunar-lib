#!/bin/sh
# lint-dockerfile.sh — agent-after-file-edit check for the docker.hadolint sub-probe.
#
# Reads the framework PostToolUse JSON payload on stdin, extracts the
# edited file path (.tool_input.file_path — Claude, Cursor, Codex, and
# Gemini all normalise to this key per lunar-probe's adapter layer), and
# runs `hadolint` against it. Exit non-zero on findings so the probe fires
# and the agent sees hadolint's diagnostic via `{check_stdout}` in the
# manifest's `message:` template. `--no-color` keeps the output readable in
# the block message (hadolint emits ANSI even when piped); stderr is folded
# into stdout so Dockerfile parse errors surface there too.
#
# hadolint is read-only by design — it has no auto-fix mode — so this
# satisfies PROBE-PLAYBOOK-AI's rule that `check:` never mutates the tree.
#
# `hadolint` presence is owned by the manifest's `requires:` block, which
# surfaces a missing linter once at session-end rather than skipping
# silently. The `command -v hadolint` guard below is defense-in-depth for
# standalone invocation (e.g. running this script outside lunar-probe).
#
# Skip-safe (exit 0, edit proceeds) when:
#   - jq isn't on PATH (can't parse the payload).
#   - hadolint isn't on PATH (standalone safety net; requires: handles the agent flow).
#   - The payload has no file_path.
#   - The file doesn't exist on disk (mid-edit race, deleted file).
#
# POSIX sh only — no bash arrays / [[ ]] / pipefail. Runs cleanly under
# dash and BusyBox sh per PROBE-PLAYBOOK-AI § "Common pitfalls".

set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v hadolint >/dev/null 2>&1 || exit 0

FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

hadolint --no-color -- "$FILE" 2>&1
