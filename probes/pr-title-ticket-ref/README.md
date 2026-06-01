# PR Title Ticket Ref Probe

Block (or warn) when an agent runs `gh pr create` with a title that
doesn't reference a ticket like `ENG-123`. Catches untraceable PRs at
authoring time so reviewers don't have to chase down the missing
context after the fact.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It ships two probes — `block` and `warn` — that intercept `gh pr create`
and check the title for a ticket reference (`[A-Z]+-\d+`, matching
Linear, Jira, and most other trackers). Both share one check script
(`scripts/check-pr-title.sh`) that parses the command line, applies
the skip rules below, and exits non-zero when the title is missing
a reference.

Consumers pick the severity by selecting a probe with `include:` /
`exclude:` on the `uses:` entry (see [Installation](#installation)).

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
  Flip `enforce_drafts: true` (see [Configuration](#configuration)) if
  your team treats drafts as real tracked work and wants the ticket
  reference from creation.
- The current branch matches a bot-author pattern: `dependabot/*` or
  `renovate/*`. These open PRs without ticket context on purpose.
- The title is prefixed with `NO-TICKET:` (case-insensitive). Use this
  for genuinely ticket-less PRs: human-cut chores, one-line README
  typo fixes, etc. The prefix itself is the audit trail.
- The title can't be parsed out of the command line at all (no
  `--title`/`-t` and no positional fallback) — the probe defers to
  `gh`'s own error handling rather than guessing.

When the title *is* present and none of the above apply, the probe
checks the title against the configured `pattern` (default
`[A-Z]+-\d+` — see [Configuration](#configuration) to override). The
block message also nudges the agent to reuse the current branch's
ticket prefix — branches named after the ticket (`feat/abc-123-...`)
are typically the easiest source.

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe) installed
and wired into your agent framework.

Add this probe to your `.lunar/probes.yml` (pin to the latest released
tag) and select **block** or **warn** with `include:`:

```yaml
version: 0

probes:
  # Hard block at gh pr create time
  - uses: github://earthly/lunar-lib/probes/pr-title-ticket-ref@v1.0.0
    include: ["block"]

  # OR: post-creation nudge instead
  # - uses: github://earthly/lunar-lib/probes/pr-title-ticket-ref@v1.0.0
  #   include: ["warn"]
```

Use `include` to select only one of the warn/block level checks (never
both at the same time). See [`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)
for the full syntax.

## Requirements

- `gh` available on the agent's `PATH`. Install via
  [cli.github.com](https://cli.github.com/) or your package manager
  (`brew install gh`, `apt-get install gh`, `dnf install gh`).
- `jq` on `PATH` for parsing the PreToolUse JSON payload that
  lunar-probe pipes to `check:` on stdin.
- POSIX `sh` — the check script is portable across Bash, dash, and
  Alpine BusyBox. No bashisms.

## Configuration

Both probes declare two inputs on the `uses:` entry; defaults are
chosen to be most-permissive so the probe stays out of the way until
you opt in to stricter behaviour.

| Input | Default | Effect |
|-------|---------|--------|
| `pattern` | `[A-Z]+-\d+` | Regex the title must match anywhere. Default covers Linear (`ENG-123`), Jira (`ABC-42`), and any other `<PROJECT>-<NUMBER>` tracker. Narrow to constrain to specific projects. |
| `enforce_drafts` | `false` | When `false`, `--draft` / `-d` invocations skip the title check (drafts are WIP, title settles before flip-to-ready). Set `true` to require the ticket reference on drafts too. |

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/pr-title-ticket-ref@v1.0.0
    include: ["block"]
    with:
      # Require leading [ENG-...] or [OPS-...] brackets specifically.
      pattern: '^\[(ENG|OPS)-\d+\]'
      # Drafts must carry the ticket too — we track them as real work.
      enforce_drafts: true
```

> `inputs:` / `with:` are currently parsed-but-reserved in
> lunar-probe — the runner accepts them without error but doesn't
> yet dispatch consumer overrides to checks (see [`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)).
> Until input dispatch ships, the check script runs against the
> declared defaults; consumer overrides will activate automatically
> once the runner supports them, without a probe-side change.

## See also

- [`policies/ticket/`](../../policies/ticket/) — CI-time policy that
  gates on collected PR data and reports missing ticket references at
  PR-check time. This probe is the agent-time complement: it intercepts
  the create call before the PR exists.
