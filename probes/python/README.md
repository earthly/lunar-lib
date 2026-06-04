# Python Probe

Agent-time Python guardrails, bundled per language. Runs
[Ruff](https://docs.astral.sh/ruff/) on every `.py` file the agent
edits — `ruff check` for lint findings (unused imports, undefined
names, pyflakes errors, pycodestyle violations, import-order and
formatting drift, and the rest of the default rule set) and
`ruff format --check` for Black-compatible formatting. Each is a
separately toggleable sub-probe.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin —
a per-language **bundle** that groups Python guardrails the same way
[`collectors/python/`](../../collectors/python/) and
[`policies/python/`](../../policies/python/) group their Python logic.
Both sub-probes hook `agent-after-file-edit` on `**/*.py`; when the agent
edits a Python file they run their Ruff command against it and, on a
non-zero exit, report the findings back to the agent as a block reason.

Consumers take the whole bundle or a subset — see
[Configuration](#configuration).

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `ruff-lint` | `agent-after-file-edit` (`paths: **/*.py`) | Run `ruff check` on the edited file, block on lint findings. |
| `ruff-format` | `agent-after-file-edit` (`paths: **/*.py`) | Run `ruff format --check` on the edited file, block on formatting drift. |

Probes auto-namespace as `<plugin>.<probe>`, so these surface as
`python.ruff-lint` and `python.ruff-format` in `lunar-probe logs`, PR
check titles, and `lunar-probe lint` output. More Python sub-probes
(e.g. a type check, a disallowed-dependency guard) can join this bundle
over time without changing how consumers reference it.

## Skip-safe behaviour

Neither sub-probe breaks the agent session when Ruff is absent — but
they don't disappear silently either. Each declares its dependency:

```yaml
requires:
  - tool: ruff
    install_hint: "pip install ruff  (or: uv tool install ruff / brew install ruff)"
```

When `ruff` isn't on `PATH`, `lunar-probe` short-circuits the check
(the edit still proceeds) and records a breadcrumb. At session-end it
surfaces a single consolidated reminder, install hint included, so a
missing linter is visible rather than a silent gap in coverage:

```
⚠ Skipped probes (missing dependencies):
- python.ruff-lint: missing `ruff` on PATH
  install: pip install ruff  (or: uv tool install ruff / brew install ruff)
```

This is `lunar-probe`'s first-class `requires:` mechanism (engine
support landed in `earthly/lunar-probe` ENG-761), not a bespoke guard —
it keeps every probe's missing-dependency reporting uniform.

## Installation

Prereq: `lunar-probe` itself must be installed on your box and wired
into your agent framework. See
[`earthly/lunar-probe` § Install](https://github.com/earthly/lunar-probe#install)
for the one-line installer; the short version is `lunar-probe install`
(auto-detects Claude Code, Cursor, Codex, Gemini), which for Claude
Code registers a native plugin via `claude plugins marketplace add` +
`claude plugins install`. Re-running `lunar-probe install` after a
lunar-probe upgrade is the supported refresh path.

Then add this bundle to your `.lunar/probes.yml` (pin to the latest
released tag):

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
```

## Requirements

- `ruff` available on the agent's `PATH`. Install via your package
  manager or `pip`: `pip install ruff`, `brew install ruff`,
  `uv tool install ruff`, or grab a static binary from
  [astral-sh/ruff releases](https://github.com/astral-sh/ruff/releases).
- `jq` on `PATH` for parsing the agent's file-edit payload.

## Configuration

Ruff reads its own configuration from the repo's `pyproject.toml` /
`ruff.toml` / `.ruff.toml` automatically — rule selection, ignores, and
line length all live there.

To take only part of the bundle, use `include:` / `exclude:` (probe
names, mutually exclusive) on the `uses:` entry:

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    exclude: [ruff-format]      # lint only — skip the format check
```

The bundle does not currently expose any `inputs:`. Surfacing knobs
for severity gating is tracked as future work.

## See also

- [`collectors/python/`](../../collectors/python/) — CI-time Python linter detection + project metadata. This bundle is the agent-time complement.
- [`policies/python/`](../../policies/python/) — policy gating on CI-collected Python linter configuration.
- [`probes/shellcheck/`](../shellcheck/) — sibling probe for shell scripts (migrating to a `probes/shell/` per-language bundle, same shape as this one).
