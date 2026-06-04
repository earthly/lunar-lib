# Shell Probe

Agent-time shell guardrails, bundled per language. Runs
[ShellCheck](https://www.shellcheck.net/) on every `.sh` file the agent
edits — the full rule set, surfaced before the change is staged.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin —
a per-language **bundle** that groups shell guardrails the same way
[`collectors/shell/`](../../collectors/shell/) and
[`policies/shell/`](../../policies/shell/) group their shell logic. The
`shellcheck` sub-probe hooks `agent-after-file-edit` on `**/*.sh`; when the
agent edits a shell script it runs ShellCheck against it and, on a non-zero
exit, reports the findings back to the agent as a block reason.

Consumers take the whole bundle or a subset — see
[Configuration](#configuration).

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `shellcheck` | `agent-after-file-edit` (`paths: **/*.sh`) | Run `shellcheck` on the edited script, block on findings. |

Probes auto-namespace as `<plugin>.<probe>`, so this surfaces as
`shell.shellcheck` in `lunar-probe logs`, PR check titles, and
`lunar-probe lint` output. More shell sub-probes (e.g. a `shfmt`
formatting check) can join this bundle over time without changing how
consumers reference it.

## Skip-safe behaviour

The `shellcheck` sub-probe never breaks the agent session when ShellCheck
is absent — but it doesn't disappear silently either. It declares its
dependency:

```yaml
requires:
  - tool: shellcheck
    install_hint: "brew install shellcheck  (or: apt-get install shellcheck / dnf install ShellCheck)"
```

When `shellcheck` isn't on `PATH`, `lunar-probe` short-circuits the check
(the edit still proceeds) and records a breadcrumb. At session-end it
surfaces a single consolidated reminder, install hint included, so a
missing linter is visible rather than a silent gap in coverage:

```
⚠ Skipped probes (missing dependencies):
- shell.shellcheck: missing `shellcheck` on PATH
  install: brew install shellcheck  (or: apt-get install shellcheck / dnf install ShellCheck)
```

This is `lunar-probe`'s first-class `requires:` mechanism (engine support
landed in `earthly/lunar-probe` ENG-761), not a bespoke guard — it keeps
every probe's missing-dependency reporting uniform.

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
  - uses: github://earthly/lunar-lib/probes/shell@v1.0.0
```

## Requirements

- `shellcheck` available on the agent's `PATH`. Install via your package
  manager: `brew install shellcheck`, `apt-get install shellcheck`,
  `dnf install ShellCheck`, or grab a static binary from
  [koalaman/shellcheck releases](https://github.com/koalaman/shellcheck/releases).
- `jq` on `PATH` for parsing the agent's file-edit payload.

## Configuration

ShellCheck reads its own configuration from the repo's `.shellcheckrc`
automatically — enabled/disabled checks, the severity floor, and shell
dialect all live there.

To take only part of the bundle, use `include:` / `exclude:` (probe
names, mutually exclusive) on the `uses:` entry:

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/shell@v1.0.0
    include: [shellcheck]       # explicit — the bundle's only probe today
```

The bundle does not currently expose any `inputs:`. A `shfmt` formatting
sub-probe (`shell.shfmt`) and severity-gating knobs are tracked as future
work.

## See also

- [`collectors/shell/`](../../collectors/shell/) — CI-time ShellCheck execution + shell language detection. This bundle is the agent-time complement.
- [`policies/shell/`](../../policies/shell/) — policy gating on CI-collected ShellCheck findings.
- [`probes/python/`](../python/) — sibling per-language probe bundle (Ruff lint + format-check), same shape as this one.
