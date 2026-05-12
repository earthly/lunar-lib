# Hadolint Probe

Lint Dockerfiles with [Hadolint](https://github.com/hadolint/hadolint) on
every edit. Catches `:latest` base tags, missing
`--no-install-recommends`, layer-cache busters, unpinned `apk add`
versions, and the rest of Hadolint's rule pack before they land in CI.

## Overview

This is a [lunar-probe](https://github.com/earthly/lunar-probe) plugin. It
wires up a single `agent-after-file-edit` hook that runs `hadolint` on any
edited Dockerfile and surfaces the findings to the agent. Hadolint is
**read-only by design** — it has no `--fix` flag — so this probe is pure
feedback. The agent decides what to do with the findings; the probe never
edits files.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `hadolint.edit` | `agent-after-file-edit` (`**/Dockerfile`, `**/Dockerfile.*`, `**/*.Dockerfile`) | Run Hadolint on the edited Dockerfile and surface any findings. |

The path list covers the three common Dockerfile naming conventions —
`Dockerfile`, `Dockerfile.dev` / `Dockerfile.prod` / etc., and
`service.Dockerfile` / `worker.Dockerfile` / etc. Matches the same find
expression the [`docker`](../../collectors/docker) collector uses at CI
time.

The probe gracefully no-ops when `hadolint` is not on `PATH` — quiet exit
in environments where the binary isn't installed.

## Installation

Add to your `.lunar/probes.yml`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/hadolint@main
```

Imported probes are namespaced as `hadolint.<probe-name>` in
`lunar-probe logs` and other surfaces. See the
[lunar-probe plugin docs](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#probe-plugins-uses-imports)
for the full `uses:` grammar, including pinning to immutable refs and
filtering with `include:` / `exclude:`.

## Requirements

`hadolint` must be on `PATH` on the developer's machine for this probe to
do anything useful:

```sh
# macOS
brew install hadolint

# Debian / Ubuntu (via GitHub releases — no apt package)
curl -sSL -o /usr/local/bin/hadolint \
  https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64
chmod +x /usr/local/bin/hadolint

# Alpine
apk add --no-cache hadolint
```

If `hadolint` is not installed, the probe silently no-ops. No error, no
nudge — just nothing happens. This makes the plugin safe to import in
mixed-environment teams where not everyone has the binary yet.

## Related

- [`collectors/docker`](../../collectors/docker) — the CI-time companion
  that runs Hadolint across every Dockerfile in the repo and writes the
  findings to `.containers.lint_results` for dashboarding.
- [`policies/container`](../../policies/container) — the CI guardrail
  whose `dockerfile-lint-clean` check fails the build on Hadolint
  findings at or above the configured severity threshold.

The probe is the **agent-time** layer of the same enforcement story:
catch issues at the moment the agent writes the Dockerfile, not on push.
