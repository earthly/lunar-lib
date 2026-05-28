# PR Title Ticket Ref Probe

Block (or warn) when an agent runs `gh pr create` with a title that
doesn't reference a ticket like `ENG-123`. Catches untraceable PRs at
authoring time so reviewers don't have to chase down the missing
context after the fact.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It ships two alternative probes — `block` and `warn` — that intercept
`gh pr create` and check the title for a ticket reference (`[A-Z]+-\d+`,
matching Linear, Jira, and most other trackers). Pick one in your
`.lunar/probes.yml`, not both. Both share a single check script
(`scripts/check-pr-title.sh`, landing in the implementation phase on
this same PR) that parses the command line, applies the skip rules
below, and exits non-zero when the title is missing a reference.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `block` | `agent-before-command` (`binary: gh`) | Block `gh pr create` when the title lacks a ticket reference. |
| `warn`  | `agent-after-command`  (`binary: gh`) | Soft-nudge alternative — warns post-creation instead of blocking. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so these show
up as `pr-title-ticket-ref.block` and `pr-title-ticket-ref.warn` in
`lunar-probe logs` and PR check titles.

> `agent-after-command` is currently a reserved hook type in
> lunar-probe — the runner parses it without error but doesn't fire it
> yet (see [`lunar-probe` § hook types](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md)).
> Once the runner ships support, `warn` activates automatically without
> a probe-side change. Until then, `block` is the only probe that fires.

## Skip-safe behaviour

The probe is a no-op (exit 0, the `gh` command proceeds) when:

- The command is not `gh pr create` — every other `gh` subcommand
  (`gh pr view`, `gh pr edit`, `gh issue create`, …) is allowed through
  unchanged. The probe parses the command line and bails before any
  title check happens.
- The invocation includes `--draft` or `-d`. Drafts are work-in-progress
  by design — humans flip the PR to ready when the title is final.
- The current branch matches a bot-author pattern: `dependabot/*` or
  `renovate/*`. These open PRs without ticket context on purpose.
- The title is prefixed with `NO-TICKET:` (case-insensitive). Use this
  for genuinely ticket-less PRs: human-cut chores, one-line README
  typo fixes, etc. The prefix itself is the audit trail.
- The title can't be parsed out of the command line at all (no
  `--title`/`-t` and no positional fallback) — the probe defers to
  `gh`'s own error handling rather than guessing.

When the title *is* present and none of the above apply, the probe
checks for `[A-Z]+-\d+` anywhere in the title. If the branch name
encodes a ticket (e.g. `bender/eng-800-...`) but the title doesn't, the
block message includes that branch as a hint.

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
released tag, and pick **either** `block` **or** `warn`, not both):

```yaml
version: 0

probes:
  # Hard block at gh pr create time
  - uses: github://earthly/lunar-lib/probes/pr-title-ticket-ref@v1.0.0
    with:
      mode: block   # reserved — see "Configuration" below

  # OR: post-creation nudge instead
  # - uses: github://earthly/lunar-lib/probes/pr-title-ticket-ref@v1.0.0
  #   with:
  #     mode: warn
```

## Requirements

- `gh` available on the agent's `PATH`. Install via
  [cli.github.com](https://cli.github.com/) or your package manager
  (`brew install gh`, `apt-get install gh`, `dnf install gh`).
- `jq` on `PATH` for parsing the PreToolUse JSON payload that
  lunar-probe pipes to `check:` on stdin.
- POSIX `sh` — the check script is portable across Bash, dash, and
  Alpine BusyBox. No bashisms.

## Configuration

The `mode` input above is **reserved for forward-compatibility** — it
maps cleanly onto a future `inputs.severity` lever that would collapse
`block` and `warn` into a single probe. Until lunar-probe ships
input-driven severity, picking the probe name (`block` vs `warn`) in
your `.lunar/probes.yml` is what actually selects the behaviour. See
[`earthly/lunar-probe` § Inputs (reserved, forward-compat)](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#inputs-reserved-forward-compat).

The ticket-reference pattern itself is hard-coded to `[A-Z]+-\d+` in
the initial release — it intentionally matches Linear (`ENG-123`),
Jira (`ABC-42`), and any other `<PROJECT>-<NUMBER>` tracker. Making
the regex configurable is tracked as a follow-up; the most common
ask would be a project-prefix allowlist (e.g. only `ENG-` or `OPS-`).

## See also

- [`policies/ticket/`](../../policies/ticket/) — CI-time policy that
  gates on collected PR data and reports missing ticket references at
  PR-check time. This probe is the agent-time complement: it intercepts
  the create call before the PR exists.
