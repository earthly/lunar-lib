# Secret Exfiltration Probe

Catch credential-exfiltration payloads in the agent loop — source that reads secrets and ships them over the network, and npm install hooks that fetch-and-execute remote code.

## Overview

When an open-source package is compromised, the damaging payload is small and recognisable: it reads secret material — API-key env vars, `~/.ssh`, `~/.aws/credentials`, `.npmrc`, `.env` — and sends it to an attacker-controlled host, or runs as an npm lifecycle install hook that executes remote code the moment you run `npm install`. This probe watches the AI agent's edit loop for both shapes and surfaces them before the code runs. `network-egress` flags a source file that both accesses secret material and contains an outbound network sink — the pairing is the exfiltration signature. `install-hook` flags a `package.json` whose `preinstall`/`install`/`postinstall`/`prepare` script fetch-and-executes remote code. It is read-only, local-only, and skip-safe.

## Probes

| Name | Hook | Description |
|------|------|-------------|
| `network-egress` | `agent-after-file-edit` | Flags a source file the agent just wrote when it both reads secret material (API-key env vars, `~/.ssh`, `~/.aws`, `.npmrc`, `.env`) and contains an outbound network sink (`fetch`, `http(s)` clients, `curl`/`wget`, raw sockets). Non-blocking warning. |
| `install-hook` | `agent-after-file-edit` | Flags a `package.json` whose `preinstall`/`install`/`postinstall`/`prepare` script fetch-and-executes remote code (`curl … \| sh`, `node -e`, `eval`, `base64 -d \| sh`) or writes to credential paths. Non-blocking warning. |

Probes auto-namespace as `<plugin>.<probe>` at runtime, so these show up as
`secret-exfil.network-egress` and `secret-exfil.install-hook` in
`lunar-probe logs`, PR check titles, and `lunar-probe lint` output.

### Why these two checks

The credential-theft step of a supply-chain compromise has a narrow, detectable
shape, and an AI coding agent is a high-value place to catch it — the agent reads,
writes, and runs untrusted third-party code on a box that holds the developer's
live credentials.

- **`network-egress`** keys on *co-occurrence*. Reading an env var is everywhere;
  making an HTTP request is everywhere. A single file that does *both* — reads a
  credential and then pushes bytes to the network — is the exfiltration payload.
  Gating on the pair (rather than either signal alone) is what keeps the
  false-positive rate low. It fires when the agent is induced to write such code,
  or vendors/pastes it from an untrusted source.
- **`install-hook`** keys on the npm lifecycle-script vector. `preinstall` /
  `install` / `postinstall` / `prepare` scripts run automatically on
  `npm install`, with no prompt — they are the primary remote-code-execution
  vector for compromised npm packages. The check flags the *dangerous body*
  (fetch-and-execute, `eval`, base64-to-shell, writes to `~/.ssh`), not the mere
  presence of a hook, so legitimate build hooks (`node scripts/build.js`,
  `husky install`, `prisma generate`) do not trip it.

### What this probe does *not* do

- It does **not** scan the contents of your installed dependencies in
  `node_modules` / site-packages — it watches what the *agent* reads, writes, and
  is about to run, not the full transitive tree. Pre-install reputation,
  maintainer-change, and known-malicious-advisory checks need network access and
  belong in a CI collector + policy, not a local probe (see *See also*).
- It is a heuristic, not a sandbox. A determined payload can be written to evade
  pattern-matching, and a legitimate file can occasionally match. It raises a
  finding for a human (or the agent) to judge; it does not guarantee safety.
- It does not block by default — both checks warn so the workflow is not
  interrupted. Pin a blocking variant in your own `.lunar/probes.yml` if you want
  a hard stop.

## Skip-safe behaviour

The probe is a no-op (exit 0, the edit proceeds) when:

- The edited file doesn't match a probe's `paths:` — `network-egress` only looks
  at source files (`.js`, `.mjs`, `.cjs`, `.ts`, `.tsx`, `.jsx`, `.py`, `.sh`,
  `.bash`, `.rb`, `.go`, `.php`, `.ps1`); `install-hook` only looks at
  `**/package.json`.
- `network-egress`: the file reads secret material **or** has a network sink but
  not both — only the co-occurrence is flagged.
- `install-hook`: the `package.json` has no lifecycle install script, or its
  script body is benign (no fetch-and-execute / obfuscation / credential-path
  write).
- The file contains the allow marker (`lunar-probe-allow: secret-exfil` by
  default) — for code that legitimately pairs a secret with a network call, for
  security advisories that quote these patterns, and for test fixtures.
- The file is larger than `max_bytes` (default 2 MiB), is binary, or no longer
  exists on disk by the time the check runs.

The checks are pure POSIX `sh` + `grep`; there is no third-party scanner to
install and no network call, so repos that carry none of these patterns never
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
  - uses: github://earthly/lunar-lib/probes/secret-exfil@main
```

Pin to a released tag (`@v1.0.0`) instead of `@main` once a `v*` release is cut.

## Requirements

- `sh` (POSIX), `grep`, and `jq` — present on virtually every developer and CI
  box. If `jq` or `grep` is missing, the probe no-ops rather than blocking.
- No third-party scanner, no network access, no API keys.

## Configuration

All inputs are optional. Set them under `with:` on the `uses:` entry in your
`.lunar/probes.yml`.

| Input | Default | Description |
|-------|---------|-------------|
| `allow_marker` | `lunar-probe-allow: secret-exfil` | Sentinel string that exempts any file containing it. Set to empty to disable the escape hatch. |
| `extra_secret_patterns` | `""` | Newline-separated POSIX ERE patterns to treat as additional secret-material access (custom token env-var names, internal credential paths). |
| `extra_egress_patterns` | `""` | Newline-separated POSIX ERE patterns to treat as additional outbound network sinks (internal HTTP wrappers, custom channels). |
| `max_bytes` | `2097152` | Files larger than this many bytes are skipped to bound scan cost. |

Example:

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/secret-exfil@main
    with:
      extra_secret_patterns: |
        ACME_DEPLOY_TOKEN
        INTERNAL_SIGNING_KEY
```

## See also

- [`secrets`](../../policies/secrets) policy — hub-side gate on secrets committed
  to the repo. This probe is the agent-time complement: it catches the code that
  would *exfiltrate* a secret, where the policy catches a secret that was
  *committed*.
- [`sca`](../../policies/sca) policy — software-composition analysis for
  dependency vulnerabilities. The network-dependent supply-chain checks this
  probe deliberately leaves out (package reputation, maintainer changes, malicious
  advisories) belong in an SCA collector + policy.
- `prompt-injection` probe — sibling agent-time security probe. Prompt-injection
  catches the *lure* that asks the agent for secrets; this probe catches the
  *payload* that ships them out.
