# ShellCheck Probe

Lint shell scripts with [ShellCheck](https://www.shellcheck.net/) on every
edit. Catches quoting bugs, deprecated syntax, command-substitution issues,
and GNU-isms before they land in CI.

## Overview

This is a [lunar-probe](https://github.com/earthly/lunar-probe) plugin. It
wires up a single `agent-after-file-edit` hook that runs `shellcheck -f tty`
on any `.sh` file the agent edits. Findings come back to the agent as the
probe `message:` body, embedding ShellCheck's terminal-style output verbatim.

ShellCheck is **read-only by design** — it has no `--fix` flag — so this
probe is pure feedback. The agent decides what to do with the findings;
the probe never edits files.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `shellcheck.edit` | `agent-after-file-edit` (`**/*.sh`) | Run ShellCheck on the edited script and surface any findings. |

The probe gracefully skips when `shellcheck` is not on `PATH` — no-op in
environments where the binary isn't installed.

## Installation

Add to your `.lunar/probes.yml`:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/shellcheck@main
```

Imported probes are namespaced as `shellcheck.<probe-name>` in
`lunar-probe logs` and other surfaces. See the
[lunar-probe plugin docs](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#probe-plugins-uses-imports)
for the full `uses:` grammar, including pinning to immutable refs and
filtering with `include:` / `exclude:`.

## Requirements

`shellcheck` must be on `PATH` on the developer's machine for this probe
to do anything useful:

```sh
# macOS
brew install shellcheck

# Debian / Ubuntu
sudo apt-get install -y shellcheck

# Alpine
apk add --no-cache shellcheck
```

If `shellcheck` is not installed, the probe silently no-ops. No error, no
nudge — just nothing happens. This makes the plugin safe to import in
mixed-environment teams where not everyone has the binary yet.

## Related

- [`collectors/shell`](../../collectors/shell) — the CI-time companion that
  collects ShellCheck output across the whole repo and writes it to
  Component JSON for dashboarding.
- [`policies/shell`](../../policies/shell) — the CI guardrail that fails
  the build on ShellCheck findings at or above the configured severity.

The probe is the **agent-time** layer of the same enforcement story: catch
issues at the moment the agent writes the file, not on push.
