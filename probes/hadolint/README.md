# hadolint Probe

Lint Dockerfiles with [hadolint](https://github.com/hadolint/hadolint)
after the agent edits a `Dockerfile*`. Runs the full default hadolint
rule set (plus its embedded ShellCheck for `RUN` blocks) against the
edited file before the change is staged — examples of what it catches
include missing `--no-install-recommends`, unpinned `apt-get install`
versions, `latest` tags, useless `cd`, and other layer-bloat patterns,
but the probe surfaces every finding hadolint reports.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It wires up a single `agent-after-file-edit` hook that fires whenever the
agent edits a file matching `**/Dockerfile*` (`Dockerfile`,
`Dockerfile.prod`, `Dockerfile.test`, etc.). The probe runs `hadolint`
against the edited file; if hadolint exits non-zero, the edit is
reported back to the agent as a block reason with the findings inlined.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `lint` | `agent-after-file-edit` (`paths: **/Dockerfile*`) | Run `hadolint` on the edited Dockerfile, block on findings. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so this one
shows up as `hadolint.lint` in `lunar-probe logs`, PR check titles,
and `lunar-probe lint` output.

## Skip-safe behaviour

The probe is a no-op (exit 0, edit proceeds) when:

- `hadolint` is not on `PATH` — repos without hadolint installed never see this probe fire.
- The edited file does not match `**/Dockerfile*`.
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
  - uses: github://earthly/lunar-lib/probes/hadolint@v1.0.0
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
override severities all live there. Surfacing knobs for severity
gating is tracked as future work.

## See also

- [`collectors/docker/`](../../collectors/docker/) — CI-time hadolint execution + Dockerfile detection. This probe is the agent-time complement.
- [`policies/container/`](../../policies/container/) — policy gating on CI-collected hadolint findings.
- [`probes/shellcheck/`](../shellcheck/) — sibling Phase 1 probe for shell scripts.
- [`probes/ruff/`](../ruff/) — sibling Phase 1 probe for Python files.
