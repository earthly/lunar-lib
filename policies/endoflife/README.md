# End-of-Life Runtime Guardrails

Enforce that components are pinned to runtime versions that upstream still maintains — catches the "neglected legacy service" smell of services running on EOL or out-of-support runtimes.

## Overview

This policy operates on data produced by the [`endoflife` collector](../../collectors/endoflife/), which detects pinned runtime versions across Node.js, Python, Ruby, Go, Java, .NET, and PHP, then resolves their EOL/support status against [endoflife.date](https://endoflife.date). Two checks: `runtime-not-eol` (no detected runtime is past its end-of-life date) and `runtime-supported` (no detected runtime is outside its active-support window). Both checks skip cleanly when no `.lang.<language>.eol` data is present (e.g. component has no detectable runtime pin, or the endoflife collector hasn't run).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `runtime-not-eol` | Fails when any `.lang.<language>.eol.is_eol` is `true` — runtime is past `eol_date`, no upstream fixes (security or otherwise) |
| `runtime-supported` | Fails when any `.lang.<language>.eol.is_supported` is `false` — runtime is past active support (may still receive security-only patches) |

`runtime-supported` is strictly stricter than `runtime-not-eol` (an EOL runtime is also unsupported). The two coexist so you can pick the strictness for your enforcement: `runtime-not-eol` for the worst-case hard-block; `runtime-supported` to catch drift early before a runtime hits security-only maintenance. For runtimes where endoflife.date doesn't expose a separate support phase (most notably Go), `is_supported` is equivalent to `not is_eol`, so the two checks behave identically for those.

If multiple runtimes are detected on the same component (rare — e.g. a service shipping a Python sidecar plus a Java app), all must pass; failures list every offending runtime. The policy currently has no tunable inputs — pass/fail thresholds are absolute (a runtime is EOL or it isn't, in active support or not). For thresholds like "fail if EOL is within N days", file a follow-up issue.

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.<language>.eol.is_eol` | boolean | `endoflife` |
| `.lang.<language>.eol.is_supported` | boolean | `endoflife` |
| `.lang.<language>.eol.cycle` | string | `endoflife` |
| `.lang.<language>.eol.detected_version` | string | `endoflife` |
| `.lang.<language>.eol.eol_date` | string \| null | `endoflife` |
| `.lang.<language>.eol.support_until` | string \| null | `endoflife` |
| `.lang.<language>.eol.product` | string | `endoflife` |

`<language>` is one of `go`, `nodejs`, `python`, `ruby`, `java`, `dotnet`, `php`. Both checks skip when no `.lang.<language>.eol` data is present for any language.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/endoflife@v1.0.0
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/endoflife@v1.0.0
    enforcement: report-pr
    # include: [runtime-not-eol]  # Only run the hard-EOL check
```

The collector and policy are paired — the policy reads `.lang.<language>.eol` data, which only the `endoflife` collector writes today. Make sure the collector is enabled wherever the policy runs.

## Examples

### Passing Example

```json
{
  "lang": {
    "nodejs": {
      "version": "20.11.1",
      "eol": {
        "source": { "tool": "endoflife.date", "integration": "api" },
        "product": "nodejs",
        "cycle": "20",
        "detected_version": "20.11.1",
        "is_eol": false,
        "is_supported": true,
        "eol_date": "2026-04-30",
        "support_until": "2025-04-30",
        "lts": true,
        "latest_in_cycle": "20.19.0"
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "go": {
      "version": "1.21",
      "eol": {
        "source": { "tool": "endoflife.date", "integration": "api" },
        "product": "go",
        "cycle": "1.21",
        "detected_version": "1.21",
        "is_eol": true,
        "is_supported": false,
        "eol_date": "2024-08-13",
        "support_until": null,
        "lts": false,
        "latest_in_cycle": "1.21.13"
      }
    }
  }
}
```

**Failure message (`runtime-not-eol`):** `go cycle 1.21 (detected 1.21) reached end-of-life on 2024-08-13. Move to a supported cycle (current latest: see https://endoflife.date/go).`

**Failure message (`runtime-supported`):** `nodejs cycle 18 (detected 18.19.1) is in security-only maintenance since 2023-10-18 and reaches end-of-life on 2025-04-30. Bump to a still-supported cycle (see https://endoflife.date/nodejs).`

## Remediation

When this policy fails, you can resolve it by:

1. **`runtime-not-eol`:** Bump the pinned runtime to a cycle whose `eol_date` is in the future. Update the relevant version file (`.go-version`, `.nvmrc`, `.python-version`, `package.json` engines, etc.) and rebuild. Reference the matching endoflife.date page (linked in the failure message) for the current latest cycle and any LTS recommendations.
2. **`runtime-supported`:** Bump the pinned runtime to a cycle that's still in active support (i.e. before `support_until`). This is the recommended fix even when the runtime isn't yet EOL — security-only maintenance is a holding pattern, not a destination.
3. **If the bump is blocked** (incompatible dependencies, planned re-platform, etc.) and you need to silence the check temporarily, configure the policy with `enforcement: report-pr` rather than `block-merge` until the upgrade lands. Don't suppress the data — leaving the EOL signal visible in the component JSON keeps the issue surfaced.

The policy does not check whether the detected version is the latest patch in its cycle (use `.lang.<language>.eol.latest_in_cycle` vs `detected_version` for a custom patch-hygiene check) and does not enforce LTS-only usage (use `.lang.<language>.eol.lts` for a custom LTS check). Example Component JSON is defined in `lunar-policy.yml` under `example_component_json`.
