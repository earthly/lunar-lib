# Lunar Plugin PR Playbook

End-to-end playbook for AI agents creating lunar-lib collector and
policy PRs. This is a **bot-mode** workflow — the agent works
autonomously through each phase, pausing only at explicit review gates.

This doc is the **overview**. The phase-by-phase deep content lives in
phase-specific docs under [`phases/`](phases/) — read the one that
matches your current phase, not all four at once.

---

## Overview

Every lunar-lib plugin PR follows this lifecycle on a **single PR**:

```text
Spec → Primary review & iterate → Secondary review → Implement & test → Review & iterate → Approval → Merge
```

| Stage | What you do | What you wait for |
|-------|------------|-------------------|
| **Spec** | Create YAML manifest, README, SVG icon. Push as draft PR. Assign the primary reviewer. | Primary reviewer comments. Address feedback. Iterate. |
| **Secondary review** | — | Primary reviewer assigns a secondary reviewer when satisfied. Wait for the secondary reviewer to approve. |
| **Go-ahead gate** | — | **The secondary reviewer approves the spec.** This is your signal — start implementing immediately. |
| **Implementation & testing** | Write code, deploy to cronos, test, gather evidence, post results, undeploy from cronos. Push to PR. | Reviewers comment. Address feedback. Spec changes may be requested even at this stage — make them and re-test. |
| **Approval gate** | — | **Both reviewers** approve the implementation via GitHub review. |
| **Merge** | Squash-merge. Re-add to cronos with `@main`. Clean up. | — |

**Never skip the spec stage.** The spec is cheap to iterate on. Code is expensive to throw away.

### How the review flow works

1. **Primary reviewer iterates on the spec.** This is the person who requested the work or was assigned first. They go back and forth with you — comments, change requests, discussion — until they're satisfied with the design.
2. **Primary reviewer assigns a secondary reviewer.** This signals the primary review is done. They wouldn't assign someone else unless they're happy.
3. **Secondary reviewer approves.** They may also request changes first — address them, then they approve.
4. **You start implementing immediately.** The secondary reviewer's approval is the trigger. **Do not ask permission. Do not re-propose a plan. Do not wait for further instructions.** Begin writing code and testing right away.

---

## Phase Index — read the one that matches your current phase

The `agent-session-start` hook in
[`.lunar/checks.yml`](../.lunar/checks.yml) (implemented by
[`.lunar/hooks/phase-guidance.sh`](../.lunar/hooks/phase-guidance.sh))
identifies the phase from the PR title and state and routes you to the
matching doc on every session start. You can also pick the phase
yourself from the table below.

| Signal | Phase | Phase doc |
|---|---|---|
| PR title contains `[Spec Only]` / `[Spec]`; no scripts (`*.sh`) in `collectors/<name>/`, no `*.py` in `policies/<name>/` | **Spec** | [`phases/spec.md`](phases/spec.md) |
| Spec approved by secondary reviewer; implementation not yet written, or just being written; test evidence not yet on the PR | **Implementation & testing** | [`phases/implementation.md`](phases/implementation.md) |
| Implementation present; cronos test evidence posted on the PR; awaiting both approvals | **Implementation review** | [`phases/impl-review.md`](phases/impl-review.md) |
| Both reviewers approved + CI green | **Merge** | [`phases/merge.md`](phases/merge.md) |

You don't have to read this overview cover-to-cover up front, but you
**must** read the matching phase doc above before starting work on
that phase. Each phase doc is self-contained for its phase — checklists,
required commands, expected evidence, and "what's next" pointers.

---

## Before You Start

These prerequisites apply once at the start of any session, regardless
of phase.

### 1. Ensure latest main

From the lunar-lib repository root:

```bash
git checkout main && git pull origin main
```

### 2. Build and install the latest Lunar CLI

Clone the `earthly/lunar` repo locally (the remote earthly target syntax `earthly github.com/earthly/lunar+build-cli` requires GitHub auth in buildkit, which cloud agents typically don't have):

```bash
# Clone once (skip if already cloned)
git clone https://github.com/earthly/lunar.git /path/to/lunar

# Build from the local clone
cd /path/to/lunar && git pull origin main
earthly +build-cli
sudo cp dist/lunar-linux-amd64 /usr/local/bin/lunar
```

### 3. Read the docs

Read the Lunar docs at https://docs-lunar.earthly.dev — this covers core concepts, CLI usage, and plugin SDKs.

Then read these files in `ai-context/` (relative to lunar-lib root):

| File | Why |
|------|-----|
| `about-lunar.md` | What Lunar is |
| `core-concepts.md` | Architecture |
| `collector-reference.md` | How collectors work (if building a collector) |
| `policy-reference.md` | How policies work (if building a policy) |
| `component-json/conventions.md` | **Schema design rules — critical.** Read the "Presence Detection" and "Anti-Pattern: Boolean Fields" sections carefully. |
| `component-json/structure.md` | All existing Component JSON paths |

### 4. Study the closest existing plugin

Find the most similar existing collector or policy and read every file. Understand the pattern before writing anything. Examples:

| If building... | Study this |
|----------------|-----------|
| Issue tracker collector | `collectors/jira/` |
| Security scanner collector | `collectors/semgrep/` or `collectors/snyk/` |
| Language collector | `collectors/golang/` or `collectors/java/` |
| Repo/file check policy | `policies/repo/` |
| Security policy | `policies/sast/` or `policies/sca/` |

---

## Common Mistakes

These are the most frequent mistakes AI agents make on lunar-lib PRs.
They cut across phases, so they live here in the overview rather than
in the phase docs. Read this section before writing any code, and
revisit it if a reviewer flags something you don't recognize.

### Component JSON schema

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Adding boolean fields (e.g. `.ci.artifacts.sbom_generated = true`) | Object presence IS the signal. If `.sbom.cicd` exists, that means SBOM was generated. A separate boolean is redundant. | Only use explicit booleans when the same collector writes both `true` and `false`. |
| Putting normalized data under `.native` | `.native.<tool>` is for raw tool-specific output. Normalized, tool-agnostic data belongs at the category level (e.g. `.sca`, `.sast`). | Move normalized fields up to the category. Keep only raw output in `.native`. |
| Inventing new top-level categories | Data may fit an existing category. | Check `component-json/structure.md` for existing categories first. |
| Naming categories after tools | Categories describe WHAT, not HOW. | `.sca`, not `.snyk`. `.sast`, not `.semgrep`. |

### Policy code

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| `return c` after `c.skip()` | `c.skip()` raises `SkippedError` which exits the `with` block immediately. `return c` is dead code and will never execute. | Remove `return c` after `c.skip()`. |
| Using `c.exists()` for skip logic | `c.exists()` raises `NoDataError` if missing — your `c.skip()` after it is unreachable. | Use `c.get_node(path).exists()` which returns `True`/`False`. |
| Calling `get_value()` without checking `exists()` | Crashes with `ValueError` if the path doesn't exist. | Always call `node.exists()` before `node.get_value()`. |
| Skipping when a sibling check already fails | Inflates the compliance score. If the guardrail IS relevant but upstream data is missing because a sibling requirement isn't met, the component should be penalized. | Let it fail (don't skip). See `ai-context/policy-reference.md` for skip vs fail guidance. |

### Collector code

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Writing empty data when nothing is found | Pollutes Component JSON. Policies evaluate against empty arrays instead of skipping. | If there's nothing to collect, write nothing. Absence of a key = feature doesn't apply. |
| Using GNU grep extensions (`-P`, `--include`) | `base-main` image is Alpine/BusyBox. GNU extensions don't exist. | Use `sed`, `find`, BusyBox-compatible patterns. |
| Using `jq` in CI collectors | CI collectors run `native` on user CI runners. `jq` may not be installed. | Use `lunar collect` with multiple key-value pairs. See existing CI collectors for patterns. |
| Exiting with `exit 1` on missing config | Fails the collector run. Users see errors for optional features. | `exit 0` with a stderr message explaining what's missing. |
| Adding cleanup code (`trap`, `rm`, temp file management) | Code collectors run in disposable Docker containers. The filesystem is thrown away when the collector finishes. | Don't bother. Use fixed paths like `/tmp/output.json`. No `mktemp` needed either. |

### SVG icons

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Using `fill="white"` or colored fills | White is invisible on GitHub's white PR diff background. Reviewers can't see the icon. | Use `fill="black"`. The website converts to white automatically. |
| Solid background rectangles | Appears as a flat rectangle on the website's dark background. | Use transparent background (no `<rect>` filling the viewBox). |
| Leaving `<title>` tags and `role="img"` | Unnecessary metadata that bloats the SVG. | Strip them. |

### PR workflow

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Starting implementation before secondary reviewer approves | The spec may change significantly during review. Implementation effort is wasted. | Wait for the secondary reviewer's approval. |
| Using `git add .` or `git add -A` | Stages unintended files (test configs, temp files, etc.). | Always `git add` specific directories: `git add collectors/<name>/` or `git add policies/<name>/`. |
| Merging with only one approval | Both reviewers need to approve unless one explicitly waives. | Wait for both. |
| Not posting test results on the PR | Reviewers need evidence, not trust. | Always post test results with JSON output, screenshots, and the test matrix template. See [`phases/implementation.md`](phases/implementation.md) Step 8. |
| Ignoring Claude review feedback | Claude auto-reviews open PRs. Unresolved comments slow down human review. | Address or reply to every Claude review comment before requesting human review. |
| Leaving branch refs in cronos config | The branch gets deleted on merge, breaking all manifest syncs. | Undeploy from cronos before merge (see [`phases/merge.md`](phases/merge.md) pre-merge checklist). |

### Docker images

| Mistake | Why it's wrong | Fix |
|---------|---------------|-----|
| Using `earthly/lunar-scripts:1.0.0` | Legacy image. | Use `earthly/lunar-lib:base-main` or `earthly/lunar-lib:<name>-main`. |
| Using `native` for code collectors | Code collectors must run in a container. | Use `earthly/lunar-lib:base-main` or a custom image. |
| Committing a temporary image tag | The tag won't exist after your test branch is cleaned up. | Always use `-main` tag in committed code. |

---

## Quick Reference: Conventions

### Component JSON paths

- **Categories describe WHAT, not HOW** — `.sca`, not `.snyk`
- **Object presence = signal** for conditional collectors (no redundant booleans)
- **Explicit booleans** only when the same collector writes both `true` and `false`
- **`.native.<tool>`** for raw tool output; normalized data at category level
- **`.source`** metadata: `{tool, version, integration}`

### PR titles

- `[Spec Only] Add <name> collector` — when the PR contains only the spec (YAML, README, icon)
- `[Implementation] Add <name> collector` — update the title once implementation is added
- No Linear ticket prefix needed for lunar-lib PRs (unlike lunar core)

---

## Improving This Document

If you encounter something unclear, make a mistake that wasn't covered
here, or discover a workaround that a future agent would benefit from
— **open a separate PR to update the relevant doc**. Don't just fix it
in your head and move on. If you think a future agent would make the
same mistake:

- Cross-cutting issues → add to [Common Mistakes](#common-mistakes) here.
- Phase-specific gotchas → add to the matching `phases/<phase>.md` doc.
- Hook gaps (something a `.lunar/checks.yml` validator could have caught) → add a hook entry too.

This is how the playbook stays useful over time.
