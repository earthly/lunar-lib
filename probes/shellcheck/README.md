# shellcheck Probe

Lint shell scripts with [ShellCheck](https://www.shellcheck.net/) after
the agent edits a `.sh` file. Runs the full ShellCheck rule set against
the edited file before the change is staged — examples of what it
catches include unquoted variables, missing `--` separators, GNU-isms
on portable shells, and useless `cat`s, but the probe surfaces every
finding ShellCheck reports.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It wires up a single `agent-after-file-edit` hook that fires whenever the
agent edits a file matching `**/*.sh`. The probe runs `shellcheck` against
the edited file; if ShellCheck exits non-zero, the edit is reported back to
the agent as a block reason with the findings inlined.

ShellCheck is **read-only by design** — there is no `--fix` flag. The
probe never rewrites the file; the agent decides how to respond.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `lint` | `agent-after-file-edit` (`paths: **/*.sh`) | Run `shellcheck` on the edited script, block on findings. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so this one
shows up as `shellcheck.lint` in `lunar-probe logs`, PR check titles,
and `lunar-probe lint` output.

## Skip-safe behaviour

The probe is a no-op (exit 0, edit proceeds) when:

- `shellcheck` is not on `PATH` — repos without ShellCheck installed never see this probe fire.
- The edited file does not match `**/*.sh`. (Shebang-based detection for extensionless scripts is tracked as a follow-up.)
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
  - uses: github://earthly/lunar-lib/probes/shellcheck@v1.0.0
```

## Requirements

- `shellcheck` available on the agent's `PATH`. Install via your package
  manager: `brew install shellcheck`, `apt-get install shellcheck`,
  `dnf install ShellCheck`, or grab a static binary from
  [koalaman/shellcheck releases](https://github.com/koalaman/shellcheck/releases).
- `jq` on `PATH` for parsing the PostToolUse payload.

## See also

- [`collectors/shell/`](../../collectors/shell/) — CI-time ShellCheck execution + shell language detection. This probe is the agent-time complement.
- [`policies/shell/`](../../policies/shell/) — policy gating on CI-collected ShellCheck findings.
