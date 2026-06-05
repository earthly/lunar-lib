# Python Probe

Agent-time guardrails for Python projects, shipped as a single
[`lunar-probe`](https://github.com/earthly/lunar-probe) plugin. Each
capability is a separate probe; select the ones you want with `include:` /
`exclude:` on the `uses:` entry.

## Overview

A growing toolkit of Python agent-time guardrails grouped under one
plugin — mirroring how [`policies/python/`](../../policies/python/) groups
Python CI-time policies. Consumers add one `uses:` entry and opt into
individual probes with `include:` (see [Installation](#installation)).
Each probe's behaviour, defaults, and configuration live on its own page
under [`docs/`](docs/).

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `ruff-lint` | `agent-after-file-edit` | Run `ruff check` on the edited `.py` file, block on lint findings. [Details →](docs/ruff-lint.md) |
| `ruff-format` | `agent-after-file-edit` | Run `ruff format --check` on the edited `.py` file, block on formatting drift. [Details →](docs/ruff-format.md) |
| `disallowed-deps` | `agent-before-file-edit` | Block dep / lock edits that pin a package to a known-vulnerable version. [Details →](docs/disallowed-deps.md) |

Probes auto-namespace as `python.<probe>` at runtime (e.g.
`python.ruff-lint`, `python.disallowed-deps`) — visible in `lunar-probe
logs` and PR check titles. More Python probes land under this plugin via
separate PRs; each adds a row here and its own page under
[`docs/`](docs/).

## Skip-safe behaviour

Every probe in this plugin is skip-safe: it's a no-op (exit `0`, the
action proceeds) whenever its trigger isn't present or the tooling it
needs is unavailable — none of them block on uncertainty.

The `ruff-*` probes additionally declare `requires: tool: ruff`. When
`ruff` isn't on `PATH`, `lunar-probe` short-circuits the check (the edit
proceeds) and surfaces a single consolidated reminder at session-end —
with an install hint — so a missing linter is visible rather than a
silent gap:

```
⚠ Skipped probes (missing dependencies):
- python.ruff-lint: missing `ruff` on PATH
  install: pip install ruff  (or: uv tool install ruff / brew install ruff)
```

The exact per-probe skip conditions are documented on each probe's page —
see [`ruff-lint`](docs/ruff-lint.md#skip-safe-behaviour),
[`ruff-format`](docs/ruff-format.md#skip-safe-behaviour), and
[`disallowed-deps`](docs/disallowed-deps.md#skip-safe-behaviour).

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe) installed
and wired into your agent framework.

Add to your `.lunar/probes.yml` (pin to a released tag) and select the
probes you want with `include:`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    include: ["ruff-lint", "ruff-format"]
```

Omit `include:` to opt into every probe the plugin ships, or use
`exclude:` to take all-but-one. See
[`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)
for the full syntax.

## Requirements

- POSIX `sh` — every check script is portable across Bash, dash, and
  Alpine BusyBox. No bashisms.
- `jq` on `PATH` for parsing the framework payload piped to each check on
  stdin.
- `ruff` on `PATH` for the `ruff-lint` / `ruff-format` probes
  (`pip install ruff`, `uv tool install ruff`, or `brew install ruff`).
  Declared via `requires:` — when absent, those probes skip and surface a
  session-end reminder rather than blocking.
- Standard text tools (`grep`, `sed`) for `disallowed-deps` —
  BusyBox-compatible flags only. No Python runtime is needed at
  agent-time.

Individual probes list their exact tooling on their [`docs/`](docs/) page.

## See also

- [`policies/python/`](../../policies/python/) — CI-time Python policies.
  The agent-time probes here are the edit-time complement: they intercept
  a problem before/at the edit, the policies catch it at PR-check time.
