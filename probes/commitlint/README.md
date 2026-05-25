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
  - uses: github://earthly/lunar-lib/probes/commitlint@v1.0.0
```

## Requirements

- `commitlint` available on the agent's `PATH` (typically installed via `npm install -g @commitlint/cli @commitlint/config-conventional` or as a devDependency invoked via `npx`).
- A commitlint config in the repo. The probe does not ship a config — it defers to whatever the repo already defines.
- `jq` on `PATH` for parsing the PreToolUse payload.

## See also

- [`collectors/git/`](../../collectors/git/) — vanilla-git Component JSON collector (gitattributes, gitmodules, signed-commits).
- [`collectors/pre-commit/`](../../collectors/pre-commit/) — pre-commit framework collector (ENG-565).
