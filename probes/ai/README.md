# AI Probe

Cap the size of AI instruction files — `AGENTS.md`, `CLAUDE.md`, and
their siblings — while the agent is editing them, so the file that
steers every future session can't quietly grow past the point where
agents stop reading it.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin,
the agent-time sibling of [`collectors/ai/`](../../collectors/ai/) and
[`policies/ai/`](../../policies/ai/). Instruction files only ever grow —
every session appends one more thing a future agent should know, nothing
ever trims — until the file stops being read and its tokens crowd out
the task. `policies/ai` reports that overage hub-side at CI time, long
after the session that caused it exited; these probes apply the same cap
inside the editing loop, where the agent can still act on it.
`instruction-file-size` rejects the oversize write,
`instruction-file-size-warn` reports it after the fact — pick one, and
see [Installation](#installation).

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `instruction-file-size` | `agent-before-file-edit` (instruction-file globs) | Block a write that would push the file past `max_lines` / `max_bytes`. Shrinking writes always allowed. |
| `instruction-file-size-warn` | `agent-after-file-edit` (same globs) | Soft-nudge alternative — reports the overage after the edit lands. |

Probes auto-namespace as `<plugin>.<probe>`, so these surface as
`ai.instruction-file-size` and `ai.instruction-file-size-warn` in
`lunar-probe logs` and PR check titles.

The globs cover the filenames agent frameworks actually read:
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
`.github/copilot-instructions.md`, and `.cursor/rules/*.{md,mdc}` — at
any depth, so a monorepo's per-package `AGENTS.md` is capped the same as
the root one.

## Skip-safe behaviour

The probe is a no-op (exit 0, the edit proceeds) when:

- The edited file doesn't match one of the instruction-file globs. Every
  other Markdown file in the repo is untouched.
- `jq` isn't on `PATH` — the check can't read the framework payload, so
  it defers rather than guessing. Declared via `requires:`, so
  lunar-probe surfaces one consolidated reminder at session end instead
  of failing silently.
- The payload carries no usable file path or content (a mid-edit race, a
  deleted file, a tool shape the adapter doesn't normalise).
- The resulting file is within `max_lines` **and** `max_bytes`.
- The write makes the file smaller than it already is. This is the
  ratchet clause: trimming an oversized instruction file is never
  blocked, so the agent can always work the file back down.
- Both caps are disabled (`max_lines: 0` and `max_bytes: 0`).

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe) installed
and wired into your agent framework (`lunar-probe install`).

Add the plugin to your `.lunar/probes.yml` (pin to the latest released
tag) and select the force level you want with `include:`:

```yaml
version: 0

probes:
  # Hard cap — reject the oversize write.
  - uses: github://earthly/lunar-lib/probes/ai@v1.0.0
    include: ["instruction-file-size"]

  # OR: report the overage instead of blocking.
  # - uses: github://earthly/lunar-lib/probes/ai@v1.0.0
  #   include: ["instruction-file-size-warn"]
```

Use `include:` to take one or the other — running both means the same
overage is reported twice per edit.

## Requirements

- `jq` on `PATH` for parsing the framework JSON payload that
  lunar-probe pipes to `check:` on stdin.
- POSIX `sh` — the check script is portable across Bash, dash, and
  Alpine BusyBox. No bashisms.

No network access, and nothing beyond the file already being edited is
read.

## Configuration

Both probes share two inputs. Defaults match the `max_lines` /
`max_total_bytes` inputs on
[`policies/ai`](../../policies/ai/)'s `instruction-file-length` check, so
the agent-time cap and the CI-time cap agree out of the box.

| Input | Default | Effect |
|-------|---------|--------|
| `max_lines` | `300` | Maximum line count for a single instruction file. `0` disables the line check. |
| `max_bytes` | `32768` | Maximum byte size for a single instruction file. `0` disables the byte check. The `ai` policy spends this budget across *all* instruction files; applying it per-file here stops one file consuming the whole allowance. |

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/ai@v1.0.0
    include: ["instruction-file-size"]
    with:
      # Tighter than the policy default — we keep AGENTS.md skimmable.
      max_lines: "150"
      # Lines are the cap we care about; don't also gate on bytes.
      max_bytes: "0"
```

Raising the ceiling is a deliberate act. If a repo keeps hitting the
cap, the usual fix is a sibling `AGENTS.md` in the subdirectory the
content actually governs, not a bigger root file.

## See also

- [`policies/ai/`](../../policies/ai/) — CI-time `instruction-file-length`
  gate (plus canonical naming, required sections, plans dir). This
  plugin is the agent-time complement and shares its thresholds.
- [`collectors/ai/`](../../collectors/ai/) — collects the instruction-file
  metrics the CI-time policy gates on.
- [`probes/pr-title-ticket-ref/`](../pr-title-ticket-ref/) — sibling
  probe bundle using the same block-or-warn pair shape.
