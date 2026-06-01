# Python Disallowed Dependencies Probe

Block agent-time edits that pin a Python dependency to a version with
a known critical CVE. Ships seeded defaults covering widely-deployed
Python CVEs (Starlette BadHost / CVE-2026-48710, urllib3, Jinja2,
PyYAML, requests, Werkzeug, aiohttp, Pillow, cryptography, setuptools);
consumers extend or replace the list per-probe via inputs.

## Overview

This is a [`lunar-probe`](https://github.com/earthly/lunar-probe) plugin.
It ships one probe, `disallowed-pin`, that hard-blocks dep-file edits
(`requirements*.txt`, `pyproject.toml`, `Pipfile*`, `poetry.lock`,
`uv.lock`) when the proposed write pins a Python package to a version
inside a known-vulnerable range.

This is the agent-time analogue of
[`policies/sbom/disallowed-packages`](../../policies/sbom/) — same mental
model (a curated disallowed list, consumers extend), applied at edit-time
on the dep files themselves rather than at PR-time on a normalized SBOM.
The shape diverges in two places (see [Notes](#notes)):

- **Per-package version ranges**, not regex-on-name — vulnerabilities are
  version-specific; regex-on-name would over-block the fix release.
- **One plugin per language** — agent-time has no normalized SBOM layer
  to abstract language, so each plugin's parser is scoped to one
  ecosystem's dep-file syntax. Sibling plugins per other language family
  (Node, Java, Go, …) will follow under the same shape.

## Probe

| Name | Hook | Description |
|------|------|-------------|
| `disallowed-pin` | `agent-before-file-edit` (dep / lock files) | Hard block — proposed write pins a Python package to a version inside a disallowed range. |

Auto-namespaces as `python-disallowed-dependencies.disallowed-pin` at
runtime (visible in `lunar-probe logs` and PR check titles).

## Shipped defaults

The probe ships with a curated list of widely-deployed Python CVEs as
`data/disallowed-dependencies.json`. Each entry is
`{name, vulnerable_range, cve, severity, fix, why}`.

> The table below is the **candidate seed list** for spec review. CVE
> IDs, exact ranges, and fix versions will be re-verified against the
> published advisories at implementation time before they land in
> `data/disallowed-dependencies.json` — these are illustrative for
> shape review, not final.

| Package | Vulnerable range | CVE | Severity | Fixed in | Issue |
|---|---|---|---|---|---|
| `starlette` | `[0.8.3, 1.0.1)` | [CVE-2026-48710](https://badhost.org/) | high | `1.0.1` | BadHost — `request.url` built from inbound `Host`; bypasses URL-path auth |
| `urllib3` | `[2.0.0, 2.2.2)` | CVE-2024-37891 | high | `2.2.2` | Proxy-auth header leaked on cross-origin redirect |
| `Jinja2` | `[0.0.0, 3.1.4)` | CVE-2024-34064 | medium | `3.1.4` | XSS via `xmlattr` filter |
| `PyYAML` | `[0.0.0, 5.4)` | CVE-2020-14343 | critical | `5.4` | RCE via `FullLoader` constructor |
| `requests` | `[2.3.0, 2.32.0)` | CVE-2024-35195 | medium | `2.32.0` | Cert verification bypass via session env |
| `Werkzeug` | `[0.0.0, 3.0.3)` | CVE-2024-34069 | medium | `3.0.3` | Debugger PIN bypass via `Host` header |
| `aiohttp` | `[0.0.0, 3.9.2)` | CVE-2024-23334 | high | `3.9.2` | Path traversal in static file serving |
| `Pillow` | `[0.0.0, 10.3.0)` | CVE-2024-28219 | high | `10.3.0` | Heap overflow in `_imagingcms` |
| `cryptography` | `[0.0.0, 42.0.0)` | CVE-2023-50782 | medium | `42.0.0` | Bleichenbacher timing attack on PKCS1v15 |
| `setuptools` | `[0.0.0, 70.0.0)` | CVE-2024-6345 | high | `70.0.0` | RCE via `package_index` download |

Defaults are kept up to date by PRs into this repo — open one to add a
new entry as new Python CVEs are published.

## Skip-safe behaviour

The probe is a no-op (exit `0`, the edit proceeds) when:

- The proposed write doesn't mention any disallowed package.
- The pinned version parses as outside the disallowed range for that
  package (already on the fix, or pre-vulnerable legacy).
- The dep-file path is parseable but the resolver can't infer a
  concrete version (e.g. an open range like `starlette` with no
  operator, or a non-PyPI source). The check defers rather than
  guessing.
- The file isn't a recognizable Python dep / lock format despite
  matching a glob (e.g. an empty or partial write). The check defers
  rather than guessing.

When the trigger *is* present and none of the above apply, the probe
fires: the edit is rejected with the offending pin on `{check_stdout}`.

## Configuration

The probe accepts two inputs that let consumers extend or replace the
shipped list without forking the plugin:

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/python-disallowed-dependencies@v1.0.0
    with:
      extra_disallowed: |
        [
          {
            "name": "django",
            "vulnerable_range": "[0.0.0, 4.2.13)",
            "cve": "CVE-2024-39329",
            "severity": "medium",
            "fix": "4.2.13",
            "why": "User enumeration via login response timing"
          }
        ]
```

| Input | Default | Notes |
|---|---|---|
| `extra_disallowed` | `[]` | JSON array, same shape as `data/disallowed-dependencies.json`. Appended to defaults. |
| `replace_defaults` | `"false"` | When `"true"`, `extra_disallowed` *replaces* shipped defaults instead of extending. |

> `inputs:` / `with:` are currently parsed-but-reserved in
> lunar-probe — the runner accepts them without error but doesn't yet
> dispatch consumer overrides to checks (see [`lunar-probe` §
> Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)).
> Until input dispatch ships, the check runs against the shipped
> defaults; consumer overrides activate automatically once the runner
> supports them, without a probe-side change.

## Installation

Prereq: [`lunar-probe`](https://github.com/earthly/lunar-probe)
installed and wired into your agent framework.

Add to your `.lunar/probes.yml` (pin to a released tag):

```yaml
version: 0

probes:
  - uses: github://earthly/lunar-lib/probes/python-disallowed-dependencies@v1.0.0
```

See [`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)
for the full syntax.

## Requirements

- POSIX `sh` — the check script is portable across Bash, dash, and
  Alpine BusyBox. No bashisms.
- `jq` on `PATH` for parsing the PreToolUse JSON payload that
  lunar-probe pipes to `check:` on stdin and for reading the
  `data/disallowed-dependencies.json` data file.
- `grep`, `sed` — BusyBox-compatible flags only (no `-P`, no
  `--include`).
- No Python runtime, no `pip` — the check parses what it needs with
  text tooling alone, keeping the probe fast and dependency-light at
  agent-time.

## Notes

- **Why one plugin per language, not per CVE.** The plugin equivalent
  at PR-time
  ([`policies/sbom/disallowed-packages`](../../policies/sbom/)) is one
  regex list applied to a normalized SBOM, which abstracts language. At
  agent-time there's no equivalent normalized layer — the probe has to
  know which dep-file syntax to parse, which is language-specific.
  Splitting by language keeps each plugin's parser scoped; future
  `node-disallowed-dependencies`, `java-disallowed-dependencies`, etc.
  follow the same shape.
- **Why per-package version ranges, not regex-on-name.** Vulnerabilities
  are version-specific; regex-on-name would over-block the fix release
  and miss the case where a known-bad range straddles a fix. The shape
  diverges from `disallowed-packages` accordingly.

## See also

- [`policies/python/`](../../policies/python/) — *(planned)* CI-time
  backstop policy that reads `.lang.python.dependencies[]` from the
  Python collector and flags vulnerable pins at PR-check time. This
  probe is the agent-time complement: it intercepts the edit before
  the bad pin lands; the policy catches the case where the pin slipped
  in some other way.
- [`policies/sbom/disallowed-packages`](../../policies/sbom/) — the
  PR-time SBOM-based equivalent that inspired this probe's shape.
- [BadHost writeup](https://badhost.org/) — CVE-2026-48710 details
  and proof-of-concept.
- [Starlette 1.0.1 release](https://github.com/encode/starlette/releases)
  — the fix.
