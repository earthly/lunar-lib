# `disallowed-deps`

A probe in the [`python`](../README.md) plugin. Runtime namespace
`python.disallowed-deps`.

Hard-blocks an `agent-before-file-edit` on Python dep / lock files
(`requirements*.txt`, `pyproject.toml`, `Pipfile*`, `poetry.lock`,
`uv.lock`) when the proposed write pins a package to a version inside a
known-vulnerable range. The agent-time analogue of
[`policies/sbom/disallowed-packages`](../../../policies/sbom/) — a curated
disallowed list, enforced on dep-file edits rather than on a PR-time SBOM.

## Shipped defaults

The probe ships a curated list of widely-deployed Python CVEs as
`data/disallowed-deps.json`. Each entry is
`{name, vulnerable_range, cve, severity, fix, why}`.

> The table below is the **candidate seed list** for spec review. CVE
> IDs, exact ranges, and fix versions get re-verified against the
> published advisories at implementation time before they land in
> `data/disallowed-deps.json` — illustrative for shape review, not final.

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
- The dep-file path is parseable but the resolver can't infer a concrete
  version (e.g. an open range like `starlette` with no operator, or a
  non-PyPI source). The check defers rather than guessing.
- The file isn't a recognizable Python dep / lock format despite matching
  a glob (e.g. an empty or partial write). The check defers rather than
  guessing.

When the trigger *is* present and none of the above apply, the probe
fires: the edit is rejected with the offending pin on `{check_stdout}`.

## Configuration

Two inputs let consumers extend or replace the shipped list without
forking the plugin:

```yaml
probes:
  - uses: github://earthly/lunar-lib/probes/python@v1.0.0
    include: ["disallowed-deps"]
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
| `extra_disallowed` | `[]` | JSON array, same shape as `data/disallowed-deps.json`. Appended to defaults. |
| `replace_defaults` | `"false"` | When `"true"`, `extra_disallowed` *replaces* shipped defaults instead of extending. |

> `inputs:` / `with:` are currently parsed-but-reserved in lunar-probe —
> the runner accepts them without error but doesn't yet dispatch consumer
> overrides to checks (see [`lunar-probe` § Uses-import](https://github.com/earthly/lunar-probe/blob/main/docs/probes-yml-syntax.md#uses-import)).
> Until input dispatch ships, the check runs against the shipped defaults;
> consumer overrides activate automatically once the runner supports them,
> without a probe-side change.

## Requirements

- POSIX `sh` — the check script is portable across Bash, dash, and Alpine
  BusyBox. No bashisms.
- `jq` on `PATH` for parsing the PreToolUse JSON payload that lunar-probe
  pipes to `check:` on stdin and for reading the
  `data/disallowed-deps.json` data file.
- `grep`, `sed` — BusyBox-compatible flags only (no `-P`, no `--include`).
- No Python runtime, no `pip` — the check parses what it needs with text
  tooling alone, keeping the probe fast and dependency-light at agent-time.

## See also

- [`policies/sbom/disallowed-packages`](../../../policies/sbom/) — the
  PR-time SBOM-based equivalent that inspired this probe's shape.
- [`policies/python/`](../../../policies/python/) — CI-time Python
  policies; a *planned* backstop policy will read
  `.lang.python.dependencies[]` from the Python collector and flag
  vulnerable pins at PR-check time.
- [BadHost writeup](https://badhost.org/) — CVE-2026-48710 details and
  proof-of-concept.
- [Starlette 1.0.1 release](https://github.com/encode/starlette/releases)
  — the fix.
