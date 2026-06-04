# docker Probe

Agent-time Docker guardrails, bundled as one `lunar-probe` plugin. The
`hadolint` sub-probe lints Dockerfiles with
[hadolint](https://github.com/hadolint/hadolint) after the agent edits
a `Dockerfile*` — full default rule set plus hadolint's embedded
ShellCheck for `RUN` blocks. Examples of what it catches include
missing `--no-install-recommends`, unpinned `apt-get install` versions,
`latest` tags, useless `cd`, and other layer-bloat patterns, but the
probe surfaces every finding hadolint reports.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It packages Docker agent guardrails as a single per-ecosystem bundle —
the same shape as [`collectors/docker/`](../../collectors/docker/) and
[`policies/container/`](../../policies/container/). Today it ships one
sub-probe (`hadolint`); future Docker checks land here as additional
sub-probes that consumers can `include:` / `exclude:` individually.

The `hadolint` sub-probe wires up an `agent-after-file-edit` hook that
fires whenever the agent edits a file matching `**/Dockerfile*`. It
runs `hadolint` against the edited file; if hadolint exits non-zero,
the edit is reported back to the agent as a block reason with the
findings inlined.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `hadolint` | `agent-after-file-edit` (`paths: **/Dockerfile*`) | Run `hadolint` on the edited Dockerfile, block on findings. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so this one
shows up as `docker.hadolint` in `lunar-probe logs`, PR check titles,
and `lunar-probe lint` output. Consumers can pin to a subset of the
bundle with `include:` / `exclude:` (see Configuration).

## Skip-safe behaviour

The `hadolint` sub-probe never breaks the agent session when hadolint
is absent — but it does **not** disappear silently either. The manifest
declares its dependency:

```yaml
requires:
  - tool: hadolint
    install_hint: "brew install hadolint  (or grab a static binary from github.com/hadolint/hadolint/releases)"
```

When `hadolint` isn't on `PATH`, `lunar-probe` short-circuits the check
(the edit still proceeds) and records a breadcrumb. At session-end it
surfaces a single consolidated reminder to the agent, install hint
included, so a missing linter is visible rather than a silent gap in
coverage:

```
⚠ Skipped probes (missing dependencies):
- docker.hadolint: missing `hadolint` on PATH
  install: brew install hadolint  (or grab a static binary from github.com/hadolint/hadolint/releases)
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

Then add this probe to your `.lunar/probes.yml` (pin to the latest
released tag):

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/docker@v1.0.0
```

## Requirements

- `hadolint` available on the agent's `PATH`. Install via your package
  manager or a static binary: `brew install hadolint`,
  `apt-get install hadolint` (newer Ubuntu), or grab a release from
  [hadolint/hadolint releases](https://github.com/hadolint/hadolint/releases).
- `jq` on `PATH` for parsing the PostToolUse payload.

## Configuration

This probe does not currently expose any `inputs:`. hadolint picks up
its configuration from `.hadolint.yaml` / `.hadolint.yml` in the repo
root automatically; per-repo rule ignores, trusted registries, and
override severities all live there.

Because the bundle is a multi-sub-probe plugin, consumers can select a
subset with the standard `include:` / `exclude:` keys — e.g. once more
Docker sub-probes ship:

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/docker@v1.0.0
    include: [hadolint]   # only run the hadolint sub-probe
```

Surfacing per-sub-probe knobs for severity gating is tracked as future
work.

## See also

- [`collectors/docker/`](../../collectors/docker/) — CI-time hadolint execution + Dockerfile detection. This probe is the agent-time complement.
- [`policies/container/`](../../policies/container/) — policy gating on CI-collected hadolint findings.
- [`probes/shellcheck/`](../shellcheck/) — sibling probe for shell scripts.
- [`probes/python/`](../python/) — sibling probe for Python files.
