# Lunar Probe Plugin Playbook

End-to-end playbook for AI agents authoring **probe plugins** in
`lunar-lib/probes/<name>/`. Probes are the fourth plugin shape in
lunar-lib, alongside collectors (`collectors/`), policies
(`policies/`), and catalogers (`catalogers/`). The PR lifecycle and
review gates are the same as collectors/policies/catalogers — see
[`LUNAR-PLUGIN-PLAYBOOK-AI.md`](LUNAR-PLUGIN-PLAYBOOK-AI.md) for the
overarching Spec → Review → Implement → Approve → Merge flow.

This doc captures what's **different** about probes. Read it together
with the main playbook; don't duplicate the cross-cutting rules here
in your head.

---

## How probes differ from collectors and policies

| Dimension | Collector | Policy | **Probe** |
|---|---|---|---|
| Where it runs | Hub-side, on a schedule (or CI) | Hub-side, against Component JSON | **Agent-side, in the live coding loop** |
| Output | Component JSON | Compliance findings | **Block reason returned to the agent** (or pass) |
| When it fires | Collection cycle / CI hook | Policy eval after collection | **Hook event** (`agent-after-file-edit`, `agent-before-command`, `agent-session-end`, …) |
| Plugin manifest | `lunar-collector.yml` | `lunar-policy.yml` | **`lunar-probe.yml`** |
| Schema home | `component-json/conventions.md` | `component-json/structure.md` | `lunar-probe`'s [`probes-yml-syntax.md`](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md) |
| Network | Often (vendor APIs, registries) | Pure-function on JSON | **Local-only** by default — no network in `check:` |
| Test cycle | Deploy to cronos, watch Component JSON | Deploy to cronos, watch policy results | **Local demo** — run the probe against a real edit / commit on the agent's box |
| Approval gate | Spec → secondary approval → implement → review → approve | Same | Same |

Two consequences that fall out of "runs in the agent loop":

1. **No Component JSON.** Skip every section of the main playbook about
   `.sca`, `.sast`, `.source`, object-presence-as-signal, etc. Probes
   don't write to Component JSON. If you find yourself reading
   `component-json/conventions.md` while authoring a probe, you're in
   the wrong doc.
2. **No cronos test cycle.** Probes don't get deployed to a hub. Test
   evidence is a transcript or screenshot of the probe firing locally —
   typically in a Claude Code session inside the consuming repo.

---

## Granularity: one bundle per language

Probes are packaged as **per-language (or per-ecosystem) bundles** —
`probes/python/`, `probes/shell/`, `probes/docker/` — each exposing one
or more **sub-probes**. This mirrors how `collectors/<language>/` and
`policies/<language>/` group their per-language logic: the directory is
the language/ecosystem, and the individual checks live inside it.

**Do not author one plugin per tool.** A `ruff` check and a future
`mypy` check are both Python guardrails, so they belong in the same
`probes/python/` bundle as two sub-probes — not in `probes/ruff/` and
`probes/mypy/`. One bundle per language keeps the integrations-page
entry, the `uses:` line a consumer writes, and the cross-reference to
the matching `collectors/<language>/` + `policies/<language>/` all
aligned on the language axis.

| Concept | What it is |
|---|---|
| **Bundle** — `probes/python/` | One directory, one `lunar-probe.yml`, one `name:` slug = the language/ecosystem. |
| **Sub-probe** — `ruff-lint`, `ruff-format` | One entry in the manifest's `probes:` list = one individual check. |

At runtime each sub-probe is namespaced `<plugin>.<probe>`, so the two
Python sub-probes surface as `python.ruff-lint` and `python.ruff-format`
in `lunar-probe logs`, PR check titles, and `lunar-probe lint` output. A
bundle can grow new sub-probes over time without changing how consumers
reference it.

> **Why the first probes diverged.** This convention was undefined when
> the shellcheck probe shipped, so it was authored per-tool
> (`probes/shellcheck/`, with a bare `lint` sub-probe). New probes follow
> the per-language convention from the start, and `probes/shellcheck/` is
> expected to fold into a `probes/shell/` bundle.

### Sub-probe naming

**Lead the sub-probe name with the tool — never a bare function name.**

| Shape | Use when | Example |
|---|---|---|
| `<tool>-<function>` | one tool exposes several distinct checks | `ruff-lint`, `ruff-format` |
| `<tool>` | the tool maps to a single check | `hadolint` |

Bare `lint` / `format` / `check` are **not** allowed. The moment a
second tool joins the bundle — a `mypy` check in `probes/python/`, a
second Dockerfile linter in `probes/docker/` — bare names collide.
Tool-scoped names (`ruff-lint` + `mypy-check`, not `lint` + `lint`) stay
unique as the bundle grows. The reference bundle `probes/python/`
(PR #188) uses this form; `probes/shellcheck/`'s bare `lint` predates the
convention.

### Consumers select sub-probes with `include:` / `exclude:`

A consumer takes the whole bundle by default, or a subset via `include:`
/ `exclude:` on the `uses:` entry. The values are bare sub-probe names,
and the two keys are **mutually exclusive** (setting both is a
`lunar-probe lint` error):

```yaml
version: 0

probes:
  # Whole bundle:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0

  # Subset — lint only, drop the format-check sub-probe:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    exclude: [ruff-format]

  # Equivalent subset, expressed as an opt-in:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    include: [ruff-lint]
```

**Reference implementation:** `probes/python/` (PR #188) — its
`lunar-probe.yml` defines the `ruff-lint` + `ruff-format` sub-probes and
its `README.md` documents the `include:` / `exclude:` selection.

---

## Layout

A probe plugin is a directory — one per language/ecosystem (see
[Granularity](#granularity-one-bundle-per-language)) — containing a
single `lunar-probe.yml` plus the assets it references:

```text
probes/<language>/
├── lunar-probe.yml        # required — plugin manifest (declares 1+ sub-probes)
├── README.md              # required — human docs
├── scripts/               # optional — referenced from check: / check_each: / check_all:
│   └── <sub-probe>.sh     # typically one script per sub-probe
└── assets/                # optional — icons / images referenced by landing_page
    └── <language>.svg
```

This mirrors the existing `collectors/<language>/` and
`policies/<language>/` shape. The differences are the manifest filename
and the absence of `requirements.txt` / `mainBash` / `mainPython` —
probes use the hook-based execution model from `lunar-probe` instead.

For the full plugin grammar, read both:

- [`earthly/lunar-probe/.agents/plans/probe-plugins.md`](https://github.com/earthly/lunar-probe/blob/main/.agents/plans/probe-plugins.md)
  — the plugin convention (manifest schema, `uses:` import forms,
  `inputs:` / `with:`, namespacing, cache, lint rules).
- [`earthly/lunar-probe/docs/probes-yml-syntax.md`](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md)
  — the `probes.yml` / `lunar-probe.yml` syntax and hook-event grammar.

---

## Manifest — `lunar-probe.yml`

Mirrors `lunar-collector.yml` / `lunar-policy.yml`. Required
top-level fields: `version`, `name`, `description`, `author`. Optional
`landing_page` block for the integrations page metadata. Required
`probes:` list, each entry binding a hook to a `check:` and a
`message:`.

```yaml
version: 0

name: <plugin-name>          # required — slug, matches directory name
description: <one-line>      # required — short human summary
author: earthly              # required — attribution

landing_page:                # optional
  display_name: "<Display Name> Probe"
  long_description: |
    Multi-line marketing description.
  categories: ["<category>", "..."]
  icon: "assets/<name>.svg"
  status: "beta"             # alpha | beta | stable
  related:
    - slug: "<sibling-plugin>"
      type: "collector"      # collector | policy | probe
      reason: "..."

inputs:                      # optional — consumer-configurable knobs
  some_flag:
    description: "..."
    default: "false"

probes:
  - name: <tool>-<function>  # required — tool-prefixed (see Sub-probe naming); runtime id is <plugin>.<name>
    description: <one-line>
    keywords: ["..."]
    hook:
      type: agent-after-file-edit   # or agent-before-command, agent-session-end, ...
      paths: "**/*.<ext>"
    requires:                       # optional — skip + session-end summary if unmet (see "Declaring dependencies")
      - tool: <bin>
        install_hint: "<how to install <bin>>"
    check: scripts/<sub-probe>.sh   # or inline shell
    message: |-
      Human-readable findings. `{check_stdout}` / `{check_stderr}` /
      `{file}` / `{files}` / `{cwd}` substitutions are available.
```

### Hook-type cheat sheet

| Hook | Fires when | Common shape |
|---|---|---|
| `agent-session-start` | Once at session start | Phase guidance, env warnings |
| `agent-after-file-edit` | After agent edits a file matching `paths:` | Per-file linters (shellcheck, ruff, prettier) |
| `agent-before-command` | Before agent runs a shell command (filter via `hook.binary.name`) | Command interceptors (commitlint, dangerous-command blockers) |
| `agent-before-tool-call` | Before any agent tool call | Tool-specific guards |
| `agent-session-end` | Once at session end | Batched / repo-wide linters (eslint, mypy) |

See [`probes-yml-syntax.md`](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md)
for the full event payload of each hook, exit-code semantics, and the
PreToolUse JSON shape piped to `check:` on stdin.

### Manifest rules — probe-specific

- **`check:` must be side-effect-free.** No `gofmt -w`, no
  `go mod tidy`, no `prettier --write`. Probes are passive sensors;
  the agent decides how to fix what's reported. Hard reviewer rule —
  enforced on Vlad's PR feedback.
- **Declare dependencies with `requires:`, not a silent `exit 0`.** If
  the probe wraps a tool — or needs a repo config file — list it under
  `requires:` (see [Declaring dependencies](#declaring-dependencies-requires)).
  `lunar-probe` then skips the check when the dependency is missing *and*
  surfaces a consolidated session-end reminder, which is strictly better
  than an in-script `command -v <tool> || exit 0` that hides the gap.
  Reserve a bare `exit 0` in the script for genuinely-inapplicable inputs
  (e.g. a matched file that no longer exists by the time `check:` runs).
- **Local-only by design.** No network calls in `check:`. If a tool
  needs network (e.g. semgrep ruleset fetch), the probe is the wrong
  shape — author it as a CI collector instead.
- **Namespacing is automatic.** Probes ship as
  `<plugin-name>.<probe-name>` in logs and PR check titles. Pick a
  plugin-level `name:` slug carefully — it's the import-time prefix.

---

## Declaring dependencies: `requires:`

A probe almost always wraps an external tool (`ruff`, `hadolint`,
`shellcheck`), and sometimes a repo config file. Declare those
dependencies with `requires:` instead of guarding for them by hand
inside the `check:` script:

```yaml
probes:
  - name: ruff-lint
    hook:
      type: agent-after-file-edit
      paths: "**/*.py"
    requires:
      - tool: ruff
        install_hint: "pip install ruff  (or: uv tool install ruff / brew install ruff)"
    check: scripts/ruff-lint.sh
    message: "Ruff found lint issues in `{file}`: `{check_stdout}`"
```

When a declared dependency is missing, `lunar-probe` **skips that
probe's check** — the edit or command still proceeds, and the skip
doesn't count toward the PR exit code — then records a breadcrumb.

Two requirement kinds; set **exactly one** per entry (both, or neither,
is a `lunar-probe lint` error):

| Kind | Met when | Example |
|---|---|---|
| `tool: <bin>` | `<bin>` is on `PATH` | `tool: ruff` |
| `config: <glob>` (or a list) | at least one glob matches a file under the repo root (a list is any-of) | `config: ["commitlint.config.*", ".commitlintrc*"]` |

`install_hint: "<string>"` is optional on either kind and is surfaced
**verbatim** in the session-end summary, so the agent sees the canonical
fix.

### The session-end summary

At `agent-session-end`, `lunar-probe` drains every breadcrumb into a
single block surfaced to the agent:

```
⚠ Skipped probes (missing dependencies):
- python.ruff-lint: missing `ruff` on PATH
  install: pip install ruff  (or: uv tool install ruff / brew install ruff)
```

This is **the sanctioned replacement for the old in-script
`command -v <tool> >/dev/null 2>&1 || exit 0` guard.** That guard made a
missing tool indistinguishable from a clean pass — coverage silently
vanished and the user never knew. `requires:` keeps the no-op behaviour
(a missing tool never breaks the session) while making the gap visible
exactly once, with the fix in hand.

### `requires:` vs `hook.when:`

Both can stop a probe from firing, but they answer different questions,
and `hook.when:` is evaluated **first**:

| Mechanism | Use when the probe… | Behaviour |
|---|---|---|
| `hook.when:` | …doesn't apply to this repo at all (e.g. a JS probe on a Go repo) | **Silent** skip — no nag |
| `requires:` | …*should* apply here, but its tool/config is missing | **Loud-on-summary** skip — session-end reminder + install hint |

If `hook.when:` gates the probe off, `requires:` isn't evaluated at all —
so a globally-installed bundle stays quiet on repos it doesn't apply to,
and only nags about a missing dependency on repos where it genuinely
should have run.

### Side-effect-free, always

`requires:` surfaces an `install_hint` string — it **never installs
anything**. This is the same rule as the read-only `check:` constraint:
probes report, the agent (or the human) acts. Don't bootstrap a tool
from inside a probe.

Reference bundles `probes/python/` (PR #188) and `probes/docker/`
(PR #189) both declare their tool with `requires:` + `install_hint:`.

---

## README

Same template as collectors/policies but with probe-shaped sections.
Required sections, in order:

1. **One-line description** under the H1.
2. **Overview** — what the probe does, what hook event it lives on,
   what it blocks vs. warns on.
3. **Probes table** — `| Name | Hook | Description |` row per probe in
   the manifest.
4. **Skip-safe behaviour** — every case where the probe is a no-op.
   Express missing-tool / missing-config cases as `requires:` and show
   the `⚠ Skipped probes` session-end summary (see
   [Declaring dependencies](#declaring-dependencies-requires)); list any
   other no-op cases (file gone mid-edit, path mismatch) as bullets.
   This is the reader's reassurance that adding the probe is low-risk.
5. **Installation** — the `uses:` one-liner for `.lunar/probes.yml`,
   pointing at `github://earthly/lunar-lib/probes/<name>@main` (and
   the tag-pinned form once a `v*` release is cut).
6. **Requirements** — local tools required (commitlint, shellcheck,
   …), and how to install them.
7. **Configuration** — `inputs:` table if present, plus a note on
   defaults. If no `inputs:` in the first release, say so and list
   planned ones as future work.
8. **See also** — sibling probes, related collectors/policies.

Spec-phase content (what the script will do, why a probe instead of a
collector+policy, etc.) lives in the **PR description**, not the
README. The published README should read as if the implementation
already exists.

---

## SVG icon

Same rules as collectors/policies:

- `fill="currentColor"` or `fill="black"` — never white, never a
  coloured fill. The website inverts to white on dark backgrounds
  automatically. Black is visible in GitHub PR diffs.
- No solid `<rect>` background — transparent.
- Strip `<title>` and `role="img"`.
- Single `<svg viewBox="0 0 100 100">` root.

Source from [simple-icons](https://github.com/simple-icons/simple-icons)
when an upstream icon exists for the tool. Otherwise hand-roll a
minimal 2–4-shape glyph at the same viewBox size — over-detailed icons
disappear at PR-comment thumbnail sizes.

---

## Spec phase — what to land in the draft PR

The Spec PR contains **only** the manifest, README, and icon. No
scripts in `scripts/`, no `requirements.txt`, no test artefacts:

```text
probes/<language>/
├── lunar-probe.yml          # declares the bundle's sub-probe(s)
├── README.md
└── assets/
    └── <language>.svg
```

Plus, if the convention itself is being extended (e.g. the first
probe in lunar-lib, or a new hook type), updates to this playbook
and/or `ai-context/`.

### PR title

```
[Spec Only] Add <name> probe
```

Once implementation lands on the same PR, retitle to:

```
[Implementation] Add <name> probe
```

### Reviewer assignment

Same two-step as collectors/policies (see
[`LUNAR-PLUGIN-PLAYBOOK-AI.md`](LUNAR-PLUGIN-PLAYBOOK-AI.md) §
"Reviewer assignment"). Add only the requester. The primary reviewer
adds a secondary when the spec is ready for the convention-level
sign-off (typically Vlad for anything that touches probe shape or
authoring rules).

---

## Implementation phase — what's different

Once the secondary reviewer approves the spec, you write the
`check:` script(s) and any required helpers, then **test locally**
(not via cronos):

1. Install `lunar-probe` from `earthly/lunar-probe` if not already on
   `PATH`. Check `lunar-probe --version` works.
2. Wire `lunar-probe` into the agent framework you're testing against
   (Claude Code is the default for lunar-lib probe development):
   ```bash
   lunar-probe install                       # auto-detects every framework on the box
   lunar-probe install --agent claude        # restrict to one framework while iterating
   lunar-probe install --dry-run             # preview without writing
   ```
   For **Claude Code**, install shells out to the `claude` CLI and
   registers `earthly/lunar-probe` as a native [Claude
   plugin](https://docs.claude.com/en/docs/claude-code/plugins):
   ```
   claude plugins marketplace add earthly/lunar-probe --sparse .claude-plugin plugins skills
   claude plugins install lunar-probe@lunar-probe
   ```
   The plugin bundle is a static artefact checked into
   `earthly/lunar-probe` (under `plugins/claude/` + the marketplace
   manifest at `.claude-plugin/marketplace.json`); the `claude` CLI
   clones the sparse subset into `~/.claude/plugins/marketplaces/...`.
   `lunar-probe install` itself doesn't write anything under
   `~/.lunar/probe/plugins/` — the only `~/.lunar/probe/` content it
   produces is the generic skill copy at
   `~/.lunar/probe/skills/<name>/`.

   Verify it landed with `claude plugins list` — you should see
   `lunar-probe@lunar-probe`. The plugin owns its own hooks, so
   `~/.claude/settings.json` is never touched (the legacy
   strip-and-rewrite was removed in
   [lunar-probe#8](https://github.com/earthly/lunar-probe/pull/8)).
   If the `claude` CLI isn't on `PATH`, install prints the two
   commands above and exits cleanly so you can run them manually
   after installing `claude`. For Cursor / Codex / Gemini, install
   writes `hooks.json` / `settings.json` directly to the framework's
   user-config dir and drops `SKILL.md` trees under each framework's
   `skills/` location.
3. In a scratch repo that exercises the probe's trigger (e.g. for
   shellcheck, a repo with at least one `.sh` file), drop a
   `.lunar/probes.yml` pointing at the local plugin path:
   ```yaml
   version: 0
   probes:
     - uses: ../lunar-lib/probes/<name>
   ```
   Local relative paths and the published
   `github://earthly/lunar-lib/probes/<name>@<ref>` form share the
   same `uses:` grammar — local during iteration, github once the
   plugin lands.
4. Trigger the probe's hook event (edit a matching file, run the
   matching command, …) and capture:
   - The full `check:` stdout/stderr.
   - The `lunar-probe logs` output for that session.
   - A pass case (probe is a no-op or exits 0).
   - A fail case (probe blocks / surfaces a finding).
   - A skip-safe case: with the tool removed from `PATH`, the edit
     proceeds and the `⚠ Skipped probes (missing dependencies)` summary
     appears at session end (the `requires:` behaviour — see
     [Declaring dependencies](#declaring-dependencies-requires)).
5. Post the captured evidence on the PR. Screenshots are fine for
   the Claude Code transcript view; text is fine for `lunar-probe
   logs` output.
6. Clean up your test box when you're done — `lunar-probe uninstall`
   (or `lunar-probe install --uninstall`) removes every entry install
   wrote, including the Claude plugin registration. User-authored
   hook entries in cursor/codex/gemini config files are preserved.

**No cronos deploy. No Component JSON screenshot. No
`bender-track-pr` for cronos sync.** Probes run client-side.

### Common implementation pitfalls

| Mistake | Why it's wrong | Fix |
|---|---|---|
| `check:` script writes to the working tree (`gofmt -w`, `prettier --write`, `go mod tidy`) | Vlad's architectural rule: `check:` is read-only. Probes are passive sensors; agent is the sole edit author. | Replace `-w` / `--write` with `-l` / `--list-different` / `--check`. Surface findings in `message:`, let the agent fix. |
| Probe fires for repos that don't use the tool | Pollutes every consumer's session with irrelevant blocks. | Declare the tool under `requires:` (see [Declaring dependencies](#declaring-dependencies-requires)) — `lunar-probe` skips the check and surfaces a session-end summary. Don't fall back to a silent in-script `command -v <tool> || exit 0`. |
| Probe writes shell that depends on bash arrays / `[[ ]]` / `set -o pipefail` semantics | Many agent shells run under POSIX `sh` (Alpine BusyBox in agent CI). | Stick to POSIX `sh` constructs. Test against `dash` or `busybox sh`. |
| Probe's `message:` lacks `{check_stdout}` / context | Agent sees a generic "probe blocked" with no recourse. | Always include the tool's output via `{check_stdout}` so the agent can act on the actual diagnostic. |
| `agent-before-command` matcher missing `binary.name` | Probe fires for every shell command, paying the parse cost for nothing. | Set `hook.binary.name: <bin>` so the probe only fires for the targeted binary. |
| Probe assumes `jq` / `yq` / GNU coreutils | Not always available. | Declare the ones the check can't run without under `requires: - tool: <bin>` so a missing one surfaces at session-end instead of crashing the check into a false positive; document all external helpers in README "Requirements" too. |

---

## Approval and merge

Same as collectors/policies:

- **Both reviewers approve** the implementation via GitHub review.
- **Squash-merge** the PR.
- **Post-merge cleanup**: branch + worktree. Probes don't have a
  cronos deployment to revert, so the cronos pre-merge / post-merge
  steps in `LUNAR-PLUGIN-PLAYBOOK-AI.md` do not apply.

---

## Quick reference

- Manifest filename: `lunar-probe.yml` (singular, matches
  `lunar-collector.yml`).
- One bundle per language/ecosystem (`probes/python/`), not one plugin
  per tool. Plugin slug `name:` = the language and must match the
  containing directory.
- Sub-probes are the entries in `probes:`; name them tool-first
  (`ruff-lint`, `ruff-format`, `hadolint`), never bare `lint` / `format`.
- Sub-probe names are auto-namespaced as `<plugin>.<probe>`
  (`python.ruff-lint`). Consumers pick a subset with `include:` /
  `exclude:` on the `uses:` entry.
- `check:` is read-only. Always.
- Declare tool/config deps with `requires:` (skips the check + surfaces
  a session-end summary) — not a silent `exit 0`. Reserve a bare
  `exit 0` for genuinely-inapplicable inputs.
- Local test only — no cronos.
- Implementation goes on the same PR as the spec after secondary
  approval.

---

## See also

- [`LUNAR-PLUGIN-PLAYBOOK-AI.md`](LUNAR-PLUGIN-PLAYBOOK-AI.md) — the
  overarching collector/policy/probe PR lifecycle and cross-cutting
  common mistakes.
- [`earthly/lunar-probe/docs/probes-yml-syntax.md`](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md)
  — authoritative `lunar-probe.yml` syntax reference.
- [`earthly/lunar-probe/.agents/plans/probe-plugins.md`](https://github.com/earthly/lunar-probe/blob/main/.agents/plans/probe-plugins.md)
  — formal plugin convention (cache, namespacing, `uses:`, lint rules).
