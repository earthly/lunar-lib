# VSCode Trust Probe

Block the repository-side artifacts behind the github.dev 1-click GitHub token-steal — workspace-local VSCode extensions and active-content notebooks.

## Overview

The github.dev 1-click GitHub token-steal runs entirely in the browser, but it only works when a repository carries two on-disk artifacts: a workspace-local VSCode extension under `.vscode/extensions/`, and a Jupyter notebook whose cells embed active HTML/JS. This probe gates both — in the AI agent's edit loop and as a PR check. `no-workspace-local-extension` hard-blocks writes to `.vscode/extensions/**/package.json`, the manifest that installs without the marketplace publisher-trust check; `notebook-active-content` flags `.ipynb` cells that render `onerror=`, `<script>`, or synthetic `KeyboardEvent`. It is read-only, local-only, and skip-safe.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `no-workspace-local-extension` | `agent-before-file-edit` | Hard-blocks writing a workspace-local VSCode extension manifest (`.vscode/extensions/**/package.json`). These install without the marketplace publisher-trust check and are the auto-install vector behind the token-steal. |
| `notebook-active-content` | `agent-after-file-edit` | Flags `.ipynb` cells embedding active HTML/JS (`onerror=`, `<script>`, synthetic `KeyboardEvent`/`dispatchEvent`) — the keystroke-injection payload shape — as a finding, and fails the same condition as a PR check. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so these show up as
`vscode-trust.no-workspace-local-extension` and
`vscode-trust.notebook-active-content` in `lunar-probe logs`, PR check titles,
and `lunar-probe lint` output.

### Why these two artifacts

The attack chain (see [the writeup](https://blog.ammaraskar.com/github-token-stealing/))
needs both pieces on disk:

- A **workspace-local extension** — extension *source* committed under
  `.vscode/extensions/<name>/package.json`. Legitimate repos recommend
  extensions through `.vscode/extensions.json`; they never ship extension
  source in-repo. An extension installed this way skips the marketplace
  publisher-trust check, and its `package.json` is also where the malicious
  `workbench.extensions.installExtension` keybinding lives — so blocking the
  manifest closes the keybinding vector too.
- An **active-content notebook** — a `.ipynb` whose markdown/output cell embeds
  HTML/JS (classically `<img src=data: onerror=...>`) that dispatches synthetic
  keystrokes. Notebook cells have no legitimate reason to carry `onerror=`,
  `<script>`, or `KeyboardEvent`.

What this probe does **not** do: it cannot stop the browser-side exploit itself
(the keystroke spoofing and token exfiltration happen in github.dev's webview,
outside any repo). It stops your repositories from becoming the delivery vehicle
and stops an AI agent from being induced to plant the payload.

## Skip-safe behaviour

The probe is a no-op (exit 0, the edit proceeds and the PR check passes) when:

- The edited or committed file doesn't match a probe's `paths:` — anything
  other than `.vscode/extensions/**/package.json` (for
  `no-workspace-local-extension`) or `**/*.ipynb` (for
  `notebook-active-content`) is ignored.
- `notebook-active-content`: the notebook contains no active-content markers
  (`onerror=`, `<script>`, `KeyboardEvent`, `dispatchEvent`).
- `no-workspace-local-extension`: a `package.json` under `.vscode/extensions/`
  that isn't actually a VSCode extension manifest (no `engines.vscode` and no
  `contributes` block) — so a coincidental path never blocks a real write.
- The file no longer exists on disk by the time the check runs (mid-edit race).

The checks are pure POSIX `sh` + `grep`; there is no third-party scanner to
install and no network call, so repos that carry none of these artifacts never
see the probe fire.

## Installation

Prereq: `lunar-probe` must be installed on your box and wired into your agent
framework. See
[`earthly/lunar-probe` § Install](https://github.com/earthly/lunar-probe#install)
for the one-line installer (`lunar-probe install` auto-detects Claude Code,
Cursor, Codex, and Gemini).

Then add this probe to your `.lunar/probes.yml`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/vscode-trust@main
```

Pin to a released tag (`@v1.0.0`) instead of `@main` once a `v*` release is cut.

## Requirements

- `lunar-probe` installed and wired into the agent framework (or run on PRs via
  the lunar-probe GitHub action).
- A POSIX `sh` and `grep` on `PATH` — both checks are pure shell, no external
  scanner required.

## Configuration

No configuration inputs in the first release. Both probes fire on a fixed set of
paths and content markers. Planned future `inputs:`:

- An allowlist of notebook paths exempt from `notebook-active-content` (for
  repos that legitimately render trusted HTML in notebooks).
- A toggle to downgrade `no-workspace-local-extension` from hard-block to
  advisory for teams that vendor a reviewed local extension.

## See also

- [The github.dev token-steal writeup](https://blog.ammaraskar.com/github-token-stealing/)
  — the attack this probe defends against.
- [`probes/shellcheck/`](../shellcheck/) and [`probes/ruff/`](../ruff/) — other
  agent-time lunar-lib probes.
- [`earthly/lunar-probe`](https://github.com/earthly/lunar-probe) — the runtime
  and `lunar-probe.yml` syntax reference.
