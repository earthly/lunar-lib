# ruff Probe

Lint Python files with [Ruff](https://docs.astral.sh/ruff/) after the
agent edits a `.py` file. Runs the full default Ruff rule set against
the edited file before the change is staged — examples of what it
catches include unused imports, undefined names, pyflakes errors,
pycodestyle violations, import-order drift, and formatting drift, but
the probe surfaces every finding Ruff reports.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It wires up a single `agent-after-file-edit` hook that fires whenever the
agent edits a file matching `**/*.py`. The probe runs `ruff check` and
`ruff format --check` against the edited file; if either exits non-zero,
the edit is reported back to the agent as a block reason with the findings
inlined.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `lint` | `agent-after-file-edit` (`paths: **/*.py`) | Run `ruff check` and `ruff format --check` on the edited file, block on findings. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so this one
shows up as `ruff.lint` in `lunar-probe logs`, PR check titles, and
`lunar-probe lint` output.

## Skip-safe behaviour

The probe is a no-op (exit 0, edit proceeds) when:

- `ruff` is not on `PATH` — repos without Ruff installed never see this probe fire.
- The edited file does not match `**/*.py`.
- The file no longer exists on disk by the time `check:` runs (mid-edit race — rare, but the script bails cleanly).

## Installation

Prereq: `lunar-probe` itself must be installed on your box and wired
into your agent framework. See
[`earthly/lunar-probe` § Install](https://github.com/earthly/lunar-probe#install)
for the one-line installer; the short version is `lunar-probe install`
(auto-detects Claude Code, Cursor, Codex, Gemini), which for Claude
Code registers a native plugin via `claude plugins marketplace add` +
`claude plugins install`. Re-running `lunar-probe install` after a
lunar-probe upgrade is the supported refresh path.

Then add this probe to your `.lunar/probes.yml` (pin to the latest
released tag):

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/ruff@v1.0.0
```

## Requirements

- `ruff` available on the agent's `PATH`. Install via your package
  manager or `pip`: `pip install ruff`, `brew install ruff`,
  `uv tool install ruff`, or grab a static binary from
  [astral-sh/ruff releases](https://github.com/astral-sh/ruff/releases).
- `jq` on `PATH` for parsing the PostToolUse payload.

## Configuration

This probe does not currently expose any `inputs:`. Ruff picks up its
configuration from the repo's `pyproject.toml` / `ruff.toml` /
`.ruff.toml` automatically; per-repo rule selection, ignored files,
and line length all live there. Surfacing knobs for severity gating
or for opting out of the format check is tracked as future work.

## See also

- [`collectors/python/`](../../collectors/python/) — CI-time Python linter detection + project metadata. This probe is the agent-time complement.
- [`policies/python/`](../../policies/python/) — policy gating on CI-collected Python linter configuration.
- [`probes/shellcheck/`](../shellcheck/) — sibling Phase 1 probe for shell scripts.
- [`probes/hadolint/`](../hadolint/) — sibling Phase 1 probe for Dockerfiles.
