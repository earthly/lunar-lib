# `.lunar/hooks/` — Scripts for Agent-Sandbox Hooks

Shell scripts referenced by `.lunar/checks.yml` entries whose logic is too involved for an inline `run:` one-liner. Each script receives a JSON payload on stdin from the agent sandbox (e.g. Claude Code) and returns exit code 0 to allow or non-zero (typically 2) to block/surface a message via stderr.

## `.lunar/checks.yml` is the source of truth

Every hook is declared in `.lunar/checks.yml`. Scripts in this directory are the *implementation* of imperative hooks. A declaration looks like this:

```yaml
- name: lunar-cli-guard
  hook: agent-before-command
  binary:
    name: lunar
  run: .lunar/hooks/lunar-cli-guard.sh
  message: "…"
```

Prefer inline `run:` for simple hooks and skip this directory entirely.

## Hook type vocabulary

All hook types follow the `<env>-<before|after>-<noun>` convention used by Lunar collector CI hooks (`ci-before-command`, `ci-after-command`, etc), with the `agent-` prefix denoting the agent-sandbox execution environment.

### Implemented in runners today

| `hook:` value | When it fires | Matcher | Framework event |
|---|---|---|---|
| `agent-session-start` | At the start of every agent session (fresh or resumed) — stdout/`message:` becomes `additionalContext` for the whole session | (none) | Claude `SessionStart` with `matcher: "startup\|resume"`; Gemini `SessionStart` |
| `agent-after-file-edit` | After agent writes or edits a file; `run:` is a real validation | `on:` (file path glob) | Claude `PostToolUse` matching `Edit\|Write`; Gemini `AfterTool` matching `write_file\|replace` |
| `agent-after-file-edit-nudge` | After agent writes or edits a file; surfaces `message:` as an advisory reminder (optionally gated by `when:`) | `on:` (glob) + optional `when:` (bash test) | same as above |
| `agent-before-command` | Before agent executes a shell command | `binary:` (structured) | Claude/Codex `PreToolUse` matching `Bash`; Gemini `BeforeTool` matching `run_shell_command` |
| `agent-before-tool-call` | Before agent invokes any named tool | `tool:` (framework tool name) | Claude/Codex `PreToolUse`; Gemini `BeforeTool` |
| `agent-session-end` | When agent session ends, if any changed file matches `on:` | `on:` (file path glob) | Claude `SessionEnd`; Codex `Stop`; Gemini `AfterAgent` |

### Reserved for future use

Schema is documented so new declarations can be written forward-compatibly; runners will add dispatch support as the need arises.

| `hook:` value | When it will fire | Matcher |
|---|---|---|
| `agent-before-file-edit` | Before agent writes/edits a file (can block or modify content) | `on:` (glob) |
| `agent-after-command` | After agent executes a shell command | `binary:` (structured) |
| `agent-after-tool-call` | After agent invokes any named tool | `tool:` (name) |
| `agent-before-prompt` | Before agent processes a user prompt | — |

### Runner implementation notes (Claude Code)

- **`agent-session-start`** maps to Claude's `SessionStart` event with `matcher: "startup|resume"` so the hook fires on fresh sessions AND on resumed sessions (`claude --resume`). This is what we want for orientation-style hooks — the agent gets the content whether the session is new or continuing. Stdout from the hook must be a JSON object of shape `{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: "..."}}`. The runner aggregates every matching entry's output.
- **`agent-session-end`** maps to `SessionEnd`, **not** `Stop`. `Stop` is a per-turn interactive-mode event (fires when the user hits esc or the agent naturally ends a turn awaiting input) and does NOT fire in `claude -p` headless/batch mode. `SessionEnd` fires in both modes. This tripped us up on PR #141 — the lint check was silently not running for months.

### Portability note

The hook *mechanism* is designed to travel across agent frameworks (Claude Code, Codex, Gemini CLI all use JSON-over-stdin + exit-2-blocks). The hook *type names* and *matcher shapes* also travel: Claude Code's `PreToolUse` and Gemini's `BeforeTool` both fire at the same semantic point.

What does NOT travel cleanly is **framework-specific tool names**:
- `agent-before-command` / `agent-after-command` are portable — runners translate to whichever tool name the current framework uses for shell execution (`Bash` on Claude/Codex, `run_shell_command` on Gemini).
- `agent-after-file-edit` is portable — runners translate to `Edit|Write` on Claude, `write_file|replace` on Gemini.
- `agent-before-tool-call` uses literal framework tool names in the `tool:` matcher. Hooks written against a Claude-specific tool (e.g. `ScheduleWakeup`) simply won't match on other frameworks — they're silently skipped rather than erroring. To support multiple frameworks, write separate entries per framework.

## Matcher shapes

### `on:` (file path glob)

For hooks that fire on file edits or on session end. Standard glob syntax, matched against the edited file's path (relative to repo root). Session-end hooks use `on:` as "any changed file in this session matches this glob" — a single match triggers the check once.

```yaml
on: "collectors/*/lunar-collector.yml"    # exact subtree
on: "policies/**/*.py"                    # recursive descent
on: "**/*.yml"                            # anything ending in .yml
```

### `when:` (nudge gate)

Only valid on `agent-after-file-edit-nudge` entries. Optional bash test expression that decides whether the nudge fires. If present, the runner executes `when:` with `{file}` substituted; the nudge surfaces only when the expression exits 0. If absent, the nudge always fires on matched files.

```yaml
# Always fires when an SVG under assets/ is edited:
- name: svg-logo-sourcing
  hook: agent-after-file-edit-nudge
  on: "**/assets/*.svg"
  message: "Reminder: check simple-icons for an official logo before creating one."

# Fires only when the edited manifest declares a CI-type hook:
- name: ci-collector-testing-reminder
  hook: agent-after-file-edit-nudge
  on: "collectors/*/lunar-collector.yml"
  when: "grep -q 'type: ci-' {file}"
  message: "Reminder: test CI collectors on cronos with a real CI run."
```

### `binary:` (structured command matcher)

For hooks that fire on shell commands. Mirrors the `ci-before-command` collector hook matcher so declarations are portable between CI and agent environments.

Today the MVP implements just `binary.name` (exact binary name match); the rest is documented for forward compatibility:

```yaml
binary:
  name: <name>              # Exact binary name match, OR
  name_pattern: <regex>     # Regex on binary name (mutually exclusive with name)
args:                       # (future) positional/flag matchers
  - value: <arg>
  - flag: <flag>
    value_pattern: <regex>
args_pattern: <regex>       # (future) regex on full args string
envs:                       # (future) env-var matchers
  - name: <var>
    value: <value>
```

The runner extracts the primary binary from the command about to execute, stripping:
- A leading `cd <path> && ...` prefix (supports unquoted, `"double"`, `'single'` quoted paths, and `~/` expansion).
- Env-var assignments (`FOO=bar CMD arg` → `CMD` is the primary binary).

## `run:` field

- A path ending in `.sh` (relative to repo root) → executed with the PreToolUse JSON on stdin.
- Anything else → executed as an inline shell expression. For file hooks, `{file}` is substituted with the edited file path before execution.

## Exit codes

- `0` → allow / check passes.
- Non-zero → block (for before-command) OR surface as a nudge/finding (for after-file-edit, session-end). See the specific runner for how non-zero is interpreted in its context.

For `agent-before-command`, non-zero stderr is propagated to the agent as the blocking message. Write them to be actionable.

## Installed hooks

### `phase-guidance.sh` — `agent-session-start`

Fires once at the start of every agent session (fresh or resumed). Emits a markdown table that routes the agent to the right section of `.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md` based on where the current PR/ticket sits in the spec → impl → merge lifecycle.

Keeps the playbook as the single source of truth — the hook's job is just to prompt the agent to identify the phase and read the right section. Prevents the "spent hours in spec phase, blew right past the implementation checklist" failure mode observed on ENG-494.

### `cronos-cheat-sheet.sh` — `agent-session-start`

Fires alongside `phase-guidance.sh` at every session start. Emits a reference distilling the non-obvious bits of the cronos testing flow — `hub.*` table schema, Grafana dashboard UIDs, canonical SQL queries, component-variable gotchas, known traps from past PRs.

Exists because implementation-phase sessions kept re-discovering the schema: "which column is `component_id`? is it the UUID or the name? where does the merged blob live?" — 10-15 Bash calls per ticket of `information_schema.columns` queries that cost compute-time without producing evidence. Distilled from BENDER-JOURNAL entries so the knowledge doesn't get re-derived every ticket.


### `lunar-cli-guard.sh` — `agent-before-command`

Blocks `lunar` CLI commands when context is wrong. Declared in `checks.yml` as `agent-before-command` matching `binary.name: lunar`. The script:

- Skips `lunar --help` / `--version` / `-h` / `-v` (they don't need hub access or a config file).
- Requires `LUNAR_HUB_TOKEN` to be set.
- For subcommands that talk to the hub or read plugin manifests (`collector`, `policy`, `component`, `catalog`, `sql`, `secret`, `hub`), requires `lunar-config.yml` or `lunar-config.yaml` in the effective working directory.
- Parses a leading `cd <path> && ...` prefix to compute the effective working directory — supports unquoted, `"double"`, and `'single'` quoted paths, plus `~/` expansion.

### `block-schedule-wakeup` (inline) — `agent-before-tool-call`

Inline `run: "exit 2"` entry that blocks Claude Code's `ScheduleWakeup` tool. No script file — the whole hook is declared in `checks.yml`.

Rationale: `ScheduleWakeup` emits a "wake me up in N seconds" event and exits, but this execution environment has no handler for those events. A scheduled wakeup turns into a silent park until the next human nudge. The hook forces agents back to `Monitor` (same-invocation polling) or exit-and-event flow.

This hook is Claude-specific (the tool name is a Claude Code built-in). Other frameworks with similar scheduling primitives would need their own entry — the matcher uses the framework's literal tool name.

## Validations vs nudges (file-edit hooks)

Use the right hook type for what you actually want:

| I want to... | Use | `run:` behavior |
|---|---|---|
| Block or flag a file that's objectively wrong | `agent-after-file-edit` | Runs a real test command; non-zero exit surfaces `message:` |
| Remind the agent about something relevant to this file | `agent-after-file-edit-nudge` | No `run:` — the `message:` is always surfaced (optionally gated by `when:`) |

Before this split, every reminder had to be written as `run: "exit 1"` with the message in `message:`, which conflated "reminder" with "validation failure" and made the intent unclear. Nudges now skip the shell dance entirely.

## Adding a new hook

1. Decide whether the logic is inline-friendly. If so, add an entry to `checks.yml` with `run: <shell>` and stop here.
2. Otherwise, drop a `*.sh` file in this directory with `#!/bin/bash` and a descriptive header comment. `chmod +x` it.
3. Add an entry in `checks.yml`:
   ```yaml
   - name: <name>
     hook: <one of the implemented types above>
     # matcher fields for the chosen type...
     run: .lunar/hooks/<script>.sh
     message: <human-readable rationale>
   ```
4. Test locally with a synthetic payload. Example shapes:
   - `agent-after-file-edit`: `{"tool_input": {"file_path": "/abs/path"}, "cwd": "/abs/cwd"}` (file path)
   - `agent-before-command`: `{"tool_input": {"command": "...", "description": "..."}, "cwd": "/abs/cwd"}` (shell command)
   - `agent-session-end`: `{"cwd": "/abs/cwd"}` (no tool-level input; runner gathers the list of changed files itself)
5. Hooks should fail fast. Agent-side runners typically cap PreToolUse execution at a few seconds across all hooks; `agent-after-file-edit` allows ~60s per check; `agent-session-end` allows ~120s.
