# End-of-Life Runtime Guardrails

Enforce that components are pinned to runtime versions that upstream still maintains. Catches the "neglected legacy service" smell — components running on a runtime that's past EOL or has dropped out of active support.

## Overview

This policy operates on data produced by the [`endoflife` collector](../../collectors/endoflife/), which detects pinned runtime versions across Node.js, Python, Ruby, Go, Java, .NET, and PHP, then resolves their EOL/support status against [endoflife.date](https://endoflife.date).

Two checks:

| Check | What it enforces |
|-------|------------------|
| `runtime-not-eol` | No detected runtime is past its end-of-life date (`is_eol == false`) |
| `runtime-supported` | No detected runtime is outside its active-support window (`is_supported == true`) |

Both checks skip cleanly when no `.lang.<language>.eol` data is present (e.g. component has no detectable runtime pin, or the endoflife collector hasn't run).

## Checks

### `runtime-not-eol`

**Fails when:** Any `.lang.<language>.eol.is_eol` is `true`.

A runtime is considered EOL when its `eol_date` (set by endoflife.date) is on or before today. Past-EOL runtimes receive no upstream fixes — including security fixes — so this is a hard "you must move off this" signal.

If multiple runtimes are detected (rare, but possible — e.g. a service shipping both a Python sidecar and a Java app), all must be non-EOL. The check fails on the first EOL runtime found and lists every offending runtime in the failure message.

**Skips when:** No `.lang.<language>.eol` data is present for any language.

### `runtime-supported`

**Fails when:** Any `.lang.<language>.eol.is_supported` is `false`.

This is a stricter version of `runtime-not-eol`. A runtime can be "not EOL" but still outside active support — e.g. Node.js 18 was in security-only maintenance for almost a full year before its hard EOL, and Python 3.10 receives security-only patches well before its 5-year EOL window closes.

For runtimes where endoflife.date doesn't expose a separate `support` field (most notably Go, which has no security-only phase), `is_supported` is equivalent to `not is_eol`, so this check behaves the same as `runtime-not-eol` for those.

Use this check when you want to catch components drifting toward EOL early — typically before the runtime hits security-only maintenance, while there's still time to bump.

**Skips when:** No `.lang.<language>.eol` data is present for any language.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/endoflife@v1.0.0
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/endoflife@v1.0.0
    enforcement: report-pr
```

The collector and policy are paired — the policy reads `.lang.<language>.eol` data, which only the `endoflife` collector writes today. Make sure the collector is enabled wherever the policy runs.

## Inputs

The policy currently has no tunable inputs. Pass/fail thresholds are absolute:

- A runtime is EOL or it isn't.
- A runtime is in active support or it isn't.

If a stricter or laxer interpretation is needed (e.g. "fail if EOL is within N days"), open a follow-up issue — the spec is intentionally minimal in v1.

## Failure messages

Both checks produce structured failure messages listing the language, the matched cycle, the detected version, and the relevant date so the fix is obvious:

```
runtime-not-eol failed: go cycle 1.21 (detected 1.21) reached end-of-life on 2024-08-13.
Move to a supported cycle (current latest: see https://endoflife.date/go).
```

```
runtime-supported failed: nodejs cycle 18 (detected 18.19.1) is in security-only maintenance
since 2023-10-18 and reaches end-of-life on 2025-04-30. Bump to a still-supported cycle
(see https://endoflife.date/nodejs).
```

## Why both checks?

You might reasonably ask: if a runtime is past EOL, isn't it also out of support? Yes — `is_eol == true` always implies `is_supported == false`. So `runtime-supported` is strictly stricter.

The two checks exist so you can pick the strictness for your enforcement:

- **`runtime-not-eol` only** — Catches the worst case (no upstream support of any kind). Often paired with `enforcement: report-pr` so dev teams see warnings but aren't blocked.
- **`runtime-supported`** — Catches drift toward EOL while there's still runway to bump. Better for production-critical services where you don't want to be on a security-only treadmill.
- **Both** — Use `runtime-not-eol` for hard-block enforcement (`enforcement: block-merge`) and `runtime-supported` for early warning (`enforcement: report-pr`).

## Notes

- The policy does not check whether the detected version is the latest patch in its cycle. That's a separate concern (a "patch hygiene" check) and isn't shipped here. Use `.lang.<language>.eol.latest_in_cycle` vs `.lang.<language>.eol.detected_version` if you want to write a custom check for that.
- The policy does not enforce LTS-only usage. `.lang.<language>.eol.lts` is exposed by the collector if you want to write a custom check requiring LTS.
- Example Component JSON is defined in `lunar-policy.yml` under `example_component_json`.
