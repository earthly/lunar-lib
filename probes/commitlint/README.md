# commitlint Probe

Lint commit messages with [commitlint](https://commitlint.js.org/) before
a `git commit` lands. Catches conventional-commits violations, length /
casing rule failures, and missing trailers at authoring time — before the
agent bounces off a `commit-msg` git-hook failure.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It wires up a single `agent-before-command` hook that intercepts every
`git commit` the agent runs, extracts the commit message from the
standard surfaces, and pipes it to `commitlint`. If commitlint exits
non-zero, the command is **blocked**; commitlint's findings come back as
the block reason.

commitlint is **read-only by design** — the probe never edits the message
or the repo's commitlint config. The agent decides how to respond; the
probe never rewrites.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `pre-commit` | `agent-before-command` (`binary: git`) | Intercept `git commit`, lint the message, block on rule violations. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so this one
shows up as `commitlint.pre-commit` in `lunar-probe logs`, PR check
titles, and `lunar-probe lint` output.

## Skip-safe behaviour

The probe is a no-op (exit 0, command proceeds) when:

- `commitlint` is not on `PATH` — repos that don't use commitlint never see this probe fire.
- No commitlint config exists in the repo (`commitlint.config.{js,cjs,mjs,ts}`, `.commitlintrc*`, or `package.json#commitlint`).
- The `git` invocation is not `commit` (e.g. `git status`, `git push`).
- The commit is `--amend` / `--no-edit` / `--squash` / merge / cherry-pick with no `-m` or `-F` — these flows go through the editor + git's own `commit-msg` hook, where commitlint should already be wired up via husky / lefthook / pre-commit.

## Installation

Add to your `.lunar/probes.yml`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/commitlint@main
```

Pin to a tag once a `v*` release is cut:

```yaml
  - uses: github://earthly/lunar-lib/probes/commitlint@v1.0.0
```

## Requirements

- `commitlint` available on the agent's `PATH` (typically installed via `npm install -g @commitlint/cli @commitlint/config-conventional` or as a devDependency invoked via `npx`).
- A commitlint config in the repo. The probe does not ship a config — it deferrs to whatever the repo already defines.
- `jq` on `PATH` for parsing the PreToolUse payload.

## Configuration

This probe has no `inputs:` in its first release. Future iterations may
add:

- `commitlint_args: "--config /path/to/override.config.js --color"` — pass through to commitlint
- `enforce_when: "config-present"` — control whether absence of a config triggers a warning vs. a no-op

Open an issue or PR if you need either before they ship.

## Implementation plan

The `check:` field references `scripts/lint-commit-message.sh`, which
will be added in the implementation phase of this PR. The script:

1. Reads the PreToolUse JSON payload from `stdin` (provided by
   `lunar-probe` per [`docs/probes-yml-syntax.md` § `agent-before-command`](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#agent-before-command)).
2. Extracts `.tool_input.command` (the full shell line the agent is about
   to run) with `jq`.
3. Skips (exit 0) when:
   - The first token is not `git`, or the next non-flag token is not `commit`.
   - The command includes `--amend`, `--no-edit`, or any flag set that
     skips the message editor (handled by git's own `commit-msg` hook
     instead).
   - `commitlint` is not on `PATH`.
   - The repo has no commitlint config file.
4. Extracts the message from `-m "..."` (single or repeated), `-F <file>`
   (reads the file), or `--file=<file>`. Handles `--` separators.
5. Pipes the message into `commitlint --no-color` (stdin form).
6. Exits with commitlint's exit code; commitlint's stdout becomes the
   `{check_stdout}` substitution in the probe `message:`.

Edge cases the script must handle:

- Multi-line messages passed as `-m "subject" -m "body"` (commitlint joins them).
- `-F -` / heredoc stdin (`<<EOF`) — capture, pipe, lint.
- Quoting / escaping in the agent's emitted command string. The PreToolUse
  payload preserves the raw command; parsing with a fragile regex would
  miss e.g. nested quotes. The implementation will use a small POSIX `sh`
  argv-tokeniser (not bash arrays — agent CI runs Alpine BusyBox).
- Repo at a path other than `$(pwd)` — `git rev-parse --show-toplevel` to
  locate the commitlint config search root.

## Why a probe, not a collector + policy?

The ticket originally called for "commitlint collector + policy plugin"
(spun out of PR #160 / ENG-565 on the call that `git` stays vanilla-git).
The structure-proposal step on this PR re-scoped commitlint as a
**probe**:

- BENDER priority #2 explicitly asks for "library of ~20 probes — basic
  programming language practices like running linters when code is edited."
  A commit-message linter is the canonical example of authoring-time
  guardrails, which is what probes are for.
- A collector+policy pair would observe commitlint configuration in the
  Component JSON at PR/CI time, but the *value* of catching a malformed
  commit is in the agent loop — *before* the commit lands — not after CI
  fails. That's the probe's lane.
- A future follow-up ticket can still add a collector+policy pair for
  CI-time enforcement (e.g. "block PR merges when commitlint config is
  missing") if the team wants a hard PR gate independent of the agent
  loop. Tracked as a "Why not also..." note rather than blocking this
  spec.

See `.ai-implementation/PROBE-PLAYBOOK-AI.md` for the broader probe
authoring convention this PR introduces.

## See also

- [`collectors/git/`](../../collectors/git/) — vanilla-git Component JSON collector (gitattributes, gitmodules, signed-commits).
- [`collectors/pre-commit/`](../../collectors/pre-commit/) — pre-commit framework collector (ENG-565).
- [`.ai-implementation/PROBE-PLAYBOOK-AI.md`](../../.ai-implementation/PROBE-PLAYBOOK-AI.md) — convention for authoring probes (this is the canonical example).

Future siblings (each tracked as a separate Linear ticket): `husky` (ENG-575), `lefthook` (ENG-576), `shellcheck` (ENG-633), `ruff` (ENG-634), `eslint` (ENG-636), `golangci-lint` (ENG-637).
