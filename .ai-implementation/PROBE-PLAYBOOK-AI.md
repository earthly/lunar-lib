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

## Layout

A probe plugin is a directory containing a single `lunar-probe.yml`
plus the assets it references:

```text
probes/<name>/
├── lunar-probe.yml        # required — plugin manifest
├── README.md              # required — human docs
├── scripts/               # optional — referenced from check: / check_each: / check_all:
│   └── <name>.sh
└── assets/                # optional — icons / images referenced by landing_page
    └── <name>.svg
```

This mirrors the existing `collectors/<name>/` and `policies/<name>/`
shape. The differences are the manifest filename and the absence of
`requirements.txt` / `mainBash` / `mainPython` — probes use the
hook-based execution model from `lunar-probe` instead.

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
  - name: <probe-name>       # required — namespaced as <plugin-name>.<probe-name> at runtime
    description: <one-line>
    keywords: ["..."]
    hook:
      type: agent-after-file-edit   # or agent-before-command, agent-session-end, ...
      paths: "**/*.<ext>"
    check: scripts/<name>.sh        # or inline shell
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
- **Default to skip-safe.** If the underlying tool isn't on `PATH` or
  the repo isn't configured for it, the probe should `exit 0` (the
  command/edit proceeds). Repos that don't use the tool should never
  see the probe fire.
- **Local-only by design.** No network calls in `check:`. If a tool
  needs network (e.g. semgrep ruleset fetch), the probe is the wrong
  shape — author it as a CI collector instead.
- **Namespacing is automatic.** Probes ship as
  `<plugin-name>.<probe-name>` in logs and PR check titles. Pick a
  plugin-level `name:` slug carefully — it's the import-time prefix.

---

## README

Same template as collectors/policies but with probe-shaped sections.
Required sections, in order:

1. **One-line description** under the H1.
2. **Overview** — what the probe does, what hook event it lives on,
   what it blocks vs. warns on.
3. **Probes table** — `| Name | Hook | Description |` row per probe in
   the manifest.
4. **Skip-safe behaviour** — bullet list of every case where the
   probe is a no-op. This is the reader's reassurance that adding the
   probe is low-risk.
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
probes/<name>/
├── lunar-probe.yml
├── README.md
└── assets/
    └── <name>.svg
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
   registers `earthly/lunar-probe` as a native plugin:
   ```
   claude plugins marketplace add earthly/lunar-probe --sparse .claude-plugin plugins skills
   claude plugins install lunar-probe@lunar-probe
   ```
   Verify it landed with `claude plugins list` — you should see
   `lunar-probe@lunar-probe`. The plugin owns its own hooks, so
   `~/.claude/settings.json` is never touched. If the `claude` CLI
   isn't on `PATH`, install prints the two commands above and exits
   cleanly so you can run them manually after installing `claude`.
   For Cursor / Codex / Gemini, install writes `hooks.json` /
   `settings.json` directly to the framework's user-config dir and
   drops `SKILL.md` trees under each framework's `skills/` location.
3. In a scratch repo that exercises the probe's trigger (e.g. for
   commitlint, a repo with a commitlint config), drop a
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
   - A skip-safe case (tool not on `PATH`, no config — probe should
     no-op).
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
| Probe fires for repos that don't use the tool | Pollutes every consumer's session with irrelevant blocks. | Add an explicit skip clause: `command -v <tool> >/dev/null 2>&1 || exit 0`. |
| Probe writes shell that depends on bash arrays / `[[ ]]` / `set -o pipefail` semantics | Many agent shells run under POSIX `sh` (Alpine BusyBox in agent CI). | Stick to POSIX `sh` constructs. Test against `dash` or `busybox sh`. |
| Probe's `message:` lacks `{check_stdout}` / context | Agent sees a generic "probe blocked" with no recourse. | Always include the tool's output via `{check_stdout}` so the agent can act on the actual diagnostic. |
| `agent-before-command` matcher missing `binary.name` | Probe fires for every shell command, paying the parse cost for nothing. | Set `hook.binary.name: <bin>` so the probe only fires for the targeted binary. |
| Probe assumes `jq` / `yq` / GNU coreutils | Not always available. | Either check with `command -v` and skip, or document the requirement in README "Requirements". |

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
- Plugin slug `name:` must match the containing directory.
- Probe names are auto-namespaced as `<plugin>.<probe>` — pick the
  plugin slug carefully.
- `check:` is read-only. Always.
- `exit 0` when the tool isn't installed or the repo isn't configured.
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
