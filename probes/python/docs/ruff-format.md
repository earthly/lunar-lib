# `ruff-format`

A probe in the [`python`](../README.md) plugin. Runtime namespace
`python.ruff-format`.

Runs [`ruff format --check`](https://docs.astral.sh/ruff/formatter/) on
every `.py` file the agent edits (`agent-after-file-edit`,
`paths: **/*.py`). When the file isn't formatted to Ruff's
(Black-compatible) standard, the edit is reported back with Ruff's output
inlined, so the agent reformats before the change lands.

## Read-only

`--check` reports whether the file *would* be reformatted and exits
non-zero on drift — it **never** rewrites the file. The agent owns the
fix (`ruff format {file}`). Per
[`PROBE-PLAYBOOK-AI`](../../../.ai-implementation/PROBE-PLAYBOOK-AI.md),
`check:` is read-only — a probe is a passive sensor, never an editor. This
is why the sub-probe is `ruff format --check` and not `ruff format`.

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
a non-zero `ruff format --check` exit, with the "Would reformat" output on
`{check_stdout}`.

## Requirements

- `ruff` on `PATH` — `pip install ruff`, `uv tool install ruff`, or
  `brew install ruff`. Declared via `requires:`.
- `jq` on `PATH` for parsing the PostToolUse JSON payload piped to
  `check:` on stdin.
- POSIX `sh` — the check script is portable across Bash, dash, and Alpine
  BusyBox.

## Configuration

No `inputs:` today. Ruff's formatter resolves its own configuration from
the repo's `pyproject.toml` / `ruff.toml` / `.ruff.toml` (e.g.
`line-length`, `quote-style`). A future input may let consumers opt out of
the format check while keeping `ruff-lint`; for now use `exclude:
["ruff-format"]` on the `uses:` entry.

## See also

- [`ruff-lint`](ruff-lint.md) — the lint companion in this plugin.
- [`collectors/python/`](../../../collectors/python/) — CI-time Python
  tooling detection. This probe is the agent-time complement.
- [Ruff formatter docs](https://docs.astral.sh/ruff/formatter/) — the
  formatting model and configuration reference.
