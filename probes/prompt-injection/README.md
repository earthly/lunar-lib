# Prompt Injection Probe

Scan files for prompt-injection markers in the agent loop — block reads
of poisoned content before it reaches the model, or warn after the agent
writes it.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin
that catches prompt-injection content in the agent loop. A
prompt-injection payload is text that tries to manipulate the agent —
override its instructions, switch its role, or trick it into leaking
secrets — rather than serve as trustworthy input, and it reaches the
agent through the untrusted content it ingests (a fetched web page, a
dependency's README, a downloaded data file). The probe scans files for
the tell-tale markers of such payloads and ships two variants, described
below.

## Probes

Both probes share one detection script (`scripts/scan-for-injection.sh`)
and differ only in when they fire and whether a hit blocks or warns.

| Name | Hook | Description |
|------|------|-------------|
| `block-read` | `agent-before-file-read` | **Blocks** the read before the agent ingests the file — the content never enters the context window. The containment play: keep the poison out of the model's input in the first place. |
| `warn-edit` | `agent-after-file-edit` | Raises a **non-blocking** warning after the agent writes a file (e.g. saving fetched web content), so it treats the content as suspect. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so these show up
as `prompt-injection.block-read` and `prompt-injection.warn-edit` in
`lunar-probe logs` and PR check titles. Select one or both with
`include:` / `exclude:` on the `uses:` entry (see [Installation](#installation)).

> **`block-read` uses the `agent-before-file-read` hook, which is
> currently reserved in lunar-probe** — the runner parses it without
> error but doesn't fire it yet (it sits under "reserved for future use"
> in the runner's hook table). Until support ships, `warn-edit` (on the
> supported `agent-after-file-edit` hook) is the variant that actually
> fires; `block-read` activates automatically once the runner dispatches
> read hooks, with no probe-side change.

### What it detects

Both variants flag the same marker families:

- **override** — "ignore all previous instructions", "disregard the above rules"
- **role-switch** — "you are now…", "pretend to be…", "developer mode", "jailbreak"
- **exfiltration** — "reveal your system prompt", "repeat the text above verbatim"
- **secret-exfil** — "send the secrets to…", "post your API key to…"
- **control-tokens** — chat-template delimiters such as `<|im_start|>`, `[INST]`, `<<SYS>>`
- **hidden-unicode** — invisible Unicode Tags-block characters (U+E0000–U+E007F)
- **extra** — any consumer-supplied patterns (see [Configuration](#configuration))

Detection is regex-based and deliberately tuned for precision over
recall — it flags the well-known injection shapes, not every conceivable
phrasing. Treat it as a high-signal tripwire, not a complete filter.

## Skip-safe behaviour

The probe is a no-op (exit 0; the read/edit proceeds) when:

- **`jq` or `grep` isn't on `PATH`** — it can't parse the payload or
  scan, so it defers rather than guess.
- **The payload has no `file_path`**, or the file doesn't exist on disk
  (mid-edit race, deleted file).
- **The file matches the allow marker.** Any file containing
  `lunar-probe-allow: prompt-injection` (configurable) is passed through
  untouched. Use it on security advisories, threat models, and docs that
  legitimately quote injection strings — including this README.
- **The file is binary** (contains a NUL byte) — injection payloads are
  text; binaries are skipped.
- **The file is larger than `max_bytes`** (default 2 MiB) — bounds scan
  cost on large blobs.
- **No marker matches** — clean files never fire.

Only the file types most likely to carry ingested/untrusted content are
in scope by default (`*.md`, `*.txt`, `*.rst`, `*.html`, `*.json`,
`*.yaml`/`*.yml`, `*.csv`, `*.xml`, and a few siblings). Source files the
agent is actively authoring are intentionally out of scope to keep the
probe quiet — add them in your own `.lunar/probes.yml` if you want them.

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe) installed
and wired into your agent framework (`lunar-probe install`).

Add this probe to your `.lunar/probes.yml` (pin to the latest released
tag) and select the variant(s) you want with `include:`:

```yaml
version: 0

probes:
  # Hard block: scan before the agent reads doc/data files
  - uses: github://earthly/lunar-lib/probes/prompt-injection@v1.0.0
    include: ["block-read"]

  # OR a softer setup: warn after writes only
  # - uses: github://earthly/lunar-lib/probes/prompt-injection@v1.0.0
  #   include: ["warn-edit"]

  # OR both — block on read, warn on write
  # - uses: github://earthly/lunar-lib/probes/prompt-injection@v1.0.0
```

Omitting `include:` loads both probes. During local development you can
point `uses:` at a relative path (`../lunar-lib/probes/prompt-injection`)
instead of the `github://` form.

## Requirements

- `jq` on `PATH` for parsing the PreToolUse/PostToolUse JSON payload that
  lunar-probe pipes to `check:` on stdin.
- `grep`, `sed`, `tr`, `wc` — POSIX text utilities, present on every
  standard system.
- POSIX `sh` — the check script is portable across Bash, dash, and Alpine
  BusyBox. No bashisms.

## Configuration

The probes declare three inputs; defaults are chosen so the probe stays
quiet until you tune it.

| Input | Default | Effect |
|-------|---------|--------|
| `allow_marker` | `lunar-probe-allow: prompt-injection` | Files containing this string anywhere are skipped. Set to `""` to disable the escape hatch. |
| `extra_patterns` | `""` | Newline-separated POSIX ERE patterns to flag on top of the built-ins, matched case-insensitively under the `extra` rule label. |
| `max_bytes` | `2097152` | Files larger than this (bytes) are skipped to bound scan cost. |

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/prompt-injection@v1.0.0
    include: ["block-read"]
    with:
      # Also flag our internal escalation phrase.
      extra_patterns: |
        run as root and disable the audit log
      # Scan files up to 5 MiB.
      max_bytes: "5242880"
```

> `inputs:` / `with:` are currently parsed-but-reserved in lunar-probe —
> the runner accepts them without error but doesn't yet dispatch consumer
> overrides to checks. Until input dispatch ships, the check script runs
> against the declared defaults (it reads each input from a
> `LUNAR_VAR_<NAME>` environment variable, so overrides activate
> automatically once the runner supports them, with no probe-side change).

## See also

- [`policies/ai/`](../../policies/ai/) — hub-side guardrails for AI
  tooling standards. This probe is the agent-time complement: it inspects
  the content entering the agent's context as the session runs.
- [`policies/secrets/`](../../policies/secrets/) — gates on leaked
  credentials in collected data. This probe catches the prompts that try
  to *exfiltrate* those credentials in the first place.
- [Anthropic — "The ways we contain Claude across products"](https://www.anthropic.com/engineering/how-we-contain-claude)
  — the containment model that motivated this probe.
