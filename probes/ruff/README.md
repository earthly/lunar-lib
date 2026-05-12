# Ruff Probe

Lint and format-check Python with [Ruff](https://github.com/astral-sh/ruff) on every agent file edit.

## Overview

This probe plugin wires [Ruff](https://github.com/astral-sh/ruff) — the
ultra-fast Rust-based Python linter + formatter — into the agent loop
via [lunar-probe](https://github.com/earthly/lunar-probe). When the
agent writes or edits a `.py` file, Ruff is invoked on that single file
and any findings are surfaced back to the agent in the next turn.

Ruff is fast enough (sub-50ms warm, per file) that per-edit feedback
fits comfortably inside the agent loop. Probes are **read-only** —
`ruff check --no-fix` and `ruff format --check` are the only commands
run; the agent owns all edits.

Replaces several legacy single-tool probes in one plugin: Ruff covers
the rule surface of flake8, isort, pylint (subset), and Black's
formatter (via `ruff format`).

## Probes

This plugin provides the following probes (use `include` / `exclude` to select a subset):

| Probe    | Hook                    | Triggers when                                            |
|----------|-------------------------|----------------------------------------------------------|
| `lint`   | `agent-after-file-edit` | The agent writes or edits a `.py` file.                  |
| `format` | `agent-after-file-edit` | Same, gated on input `format_check` (default `"true"`).  |

Both probes silently no-op when `ruff` is not installed on the consumer's
machine (`command -v ruff` guard).

## Inputs

| Input          | Default  | Description                                                                                  |
|----------------|----------|----------------------------------------------------------------------------------------------|
| `format_check` | `"true"` | If `"true"`, also run `ruff format --check`. Set to `"false"` to skip the `format` probe.    |

## Prerequisites

The consumer's environment must have `ruff` on `PATH`. Recommended install:

```bash
pip install ruff
# or
uv tool install ruff
# or
brew install ruff
```

If `ruff` isn't installed, both probes silently no-op (they don't error
or block the agent) — the plugin is safe to import speculatively.

## Installation

Add to your `.lunar/probes.yml`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/ruff@main
    # exclude: [format]                          # Skip the format probe (alternative to format_check=false)
    # with:
    #   format_check: "false"                    # Disable format probe; keep lint
```

Then run `lunar-probe install` to fetch the plugin and wire it into your
agent framework (Claude Code, Cursor, Codex, Gemini CLI).

## Side-effect policy

Probes are passive sensors — they never write to files. The commands
used are read-only:

* **Lint**: `ruff check --quiet --no-fix {file}` — `--no-fix` prevents
  Ruff from applying its auto-fixes.
* **Format**: `ruff format --check --quiet {file}` — `--check` reports
  diffs without rewriting the file.

If the agent wants Ruff's auto-fixes, it can run `ruff check --fix` or
`ruff format` itself as part of an explicit edit, then re-read the file.
