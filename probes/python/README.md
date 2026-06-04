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
| `disallowed-deps` | `agent-before-file-edit` | Block dep / lock edits that pin a package to a known-vulnerable version. [Details →](docs/disallowed-deps.md) |

Probes auto-namespace as `python.<probe>` at runtime (e.g.
`python.disallowed-deps`) — visible in `lunar-probe logs` and PR check
titles. More Python probes (a linter, a CVE code-pattern nudge, …) land
under this plugin via separate PRs; each adds a row here and its own page
under [`docs/`](docs/).

## Skip-safe behaviour

Every probe in this plugin is skip-safe: it's a no-op (exit `0`, the
action proceeds) whenever its trigger isn't present or the tooling it
needs is unavailable — none of them block on uncertainty. The exact skip
conditions are documented per probe — see
[`disallowed-deps` § Skip-safe behaviour](docs/disallowed-deps.md#skip-safe-behaviour).

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe) installed
and wired into your agent framework.

Add to your `.lunar/probes.yml` (pin to a released tag) and select the
probes you want with `include:`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    include: ["disallowed-deps"]
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
- Standard text tools (`grep`, `sed`, `awk`) — BusyBox-compatible flags
  only. No Python runtime is needed at agent-time.

Individual probes may list extra tools on their [`docs/`](docs/) page.

## See also

- [`policies/python/`](../../policies/python/) — CI-time Python policies.
  The agent-time probes here are the edit-time complement: they intercept
  a problem before the edit lands, the policies catch it at PR-check time.
