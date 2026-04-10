# GitHub Actions Security Collector

Statically analyzes GitHub Actions workflows for security misconfigurations and injection risks.

## Overview

Parses all workflow files in `.github/workflows/` and extracts security-relevant findings without executing anything. Detects template injection risks (`${{ }}` expressions in `run:` blocks), dangerous `pull_request_target` + checkout combinations, missing or overly broad permissions, credential persistence in `actions/checkout`, and `secrets: inherit` in reusable workflow calls. Independent from the `github-actions` collector (which covers lint and pinning) — no overlap with the existing `ci` policy. Skips gracefully if no workflows directory exists.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ci.security.source` | object | Tool metadata (`tool`, `version`, `integration`) |
| `.ci.security.injectable_expressions[]` | array | `${{ }}` expressions in `run:` blocks using attacker-controllable contexts |
| `.ci.security.dangerous_checkouts[]` | array | `pull_request_target` workflows that check out PR head code |
| `.ci.security.permissions_missing[]` | array | Workflows with no explicit `permissions:` key |
| `.ci.security.write_all_permissions[]` | array | Workflows or jobs with `permissions: write-all` |
| `.ci.security.persist_credentials[]` | array | `actions/checkout` steps without `persist-credentials: false` |
| `.ci.security.secrets_inherit[]` | array | Reusable workflow calls using `secrets: inherit` |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `security` | Analyzes all workflow files for injection risks, permission issues, and insecure patterns |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gha-security@main
    on: ["domain:your-domain"]
```

