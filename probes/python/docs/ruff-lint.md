# `ruff-lint`

A probe in the [`python`](../README.md) plugin. Runtime namespace
`python.ruff-lint`.

Runs [`ruff check`](https://docs.astral.sh/ruff/linter/) on every `.py`
file the agent edits (`agent-after-file-edit`, `paths: **/*.py`). On any
finding the edit is reported back with Ruff's diagnostic inlined, so the
agent fixes it before the change lands. The agent-time complement of the
CI-time linter detection in [`collectors/python/`](../../../collectors/python/).

Ruff runs the full default rule set — Pyflakes (`F`), a pycodestyle
subset (`E`/`W`), and more — plus whatever the repo opts into via its
`pyproject.toml` / `ruff.toml` / `.ruff.toml`. Examples of what it
catches: unused imports, undefined names, redefinitions, and unparseable
syntax. The probe surfaces every finding Ruff reports, not a curated
subset.

## Read-only

The probe runs `ruff check` **without** `--fix`. It reports findings; it
never rewrites the file. Per
[`PROBE-PLAYBOOK-AI`](../../../.ai-implementation/PROBE-PLAYBOOK-AI.md),
`check:` is a passive sensor — the agent owns every edit.

## Skip-safe behaviour

The probe is a no-op (exit `0`, the edit proceeds) when:

- `ruff` isn't on `PATH`. This is declared via `requires: tool: ruff`, so
  rather than skipping silently `lunar-probe` records a breadcrumb and
  surfaces one consolidated reminder — with an install hint — at
  session-end. (The check script also guards `command -v ruff` as a
  standalone backstop.)
- `jq` isn't on `PATH` (can't parse the payload).
- The payload carries no file path.
- The file no longer exists on disk by the time the check runs (mid-edit
  race, deleted file).

When the trigger *is* present and `ruff` is installed, the probe fires on
a non-zero `ruff check` exit, with the findings on `{check_stdout}`.

## Requirements

- `ruff` on `PATH` — `pip install ruff`, `uv tool install ruff`, or
  `brew install ruff`. Declared via `requires:`.
- `jq` on `PATH` for parsing the PostToolUse JSON payload piped to
  `check:` on stdin.
- POSIX `sh` — the check script is portable across Bash, dash, and Alpine
  BusyBox.

## Configuration

No `inputs:` today. Ruff resolves its own configuration from the repo's
`pyproject.toml` / `ruff.toml` / `.ruff.toml` — rule selection, ignores,
target version, and line length all live there. Surfacing knobs for
severity gating is tracked as future work.

## See also

- [`ruff-format`](ruff-format.md) — the formatting-drift companion in this
  plugin.
- [`collectors/python/`](../../../collectors/python/) — CI-time Python
  linter detection. This probe is the agent-time complement.
- [Ruff linter docs](https://docs.astral.sh/ruff/linter/) — the rule
  catalogue and configuration reference.
