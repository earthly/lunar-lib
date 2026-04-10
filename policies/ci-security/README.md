# CI Security Guardrails

Enforces GitHub Actions security best practices — injection prevention, least-privilege permissions, and credential hygiene.

## Overview

Checks GitHub Actions workflows for six categories of security misconfiguration that have led to real-world supply chain compromises. All checks are based on static YAML analysis — no runtime data needed. Skips gracefully when no GitHub Actions security data is available (i.e., component has no `.github/workflows/` directory). Different from the existing `ci` policy (which covers action pinning and mutable refs — no overlap) and the `sast` policy (which covers application code analysis, not CI configuration).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `no-script-injection` | Flags attacker-controlled `${{ }}` expressions in `run:` blocks |
| `no-dangerous-trigger-checkout` | Flags `pull_request_target` workflows that check out PR head code |
| `permissions-declared` | Flags workflows with no explicit `permissions:` key |
| `no-write-all-permissions` | Flags `permissions: write-all` at workflow or job level |
| `checkout-no-persist-credentials` | Flags `actions/checkout` without `persist-credentials: false` |
| `no-secrets-inherit` | Flags `secrets: inherit` in reusable workflow calls |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.ci.security.injectable_expressions` | array | `gha-security` collector |
| `.ci.security.dangerous_checkouts` | array | `gha-security` collector |
| `.ci.security.permissions_missing` | array | `gha-security` collector |
| `.ci.security.write_all_permissions` | array | `gha-security` collector |
| `.ci.security.persist_credentials` | array | `gha-security` collector |
| `.ci.security.secrets_inherit` | array | `gha-security` collector |

**Note:** Ensure the `gha-security` collector is configured before enabling this policy.

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gha-security@main
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/ci-security@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [no-script-injection, permissions-declared]  # Run specific checks only
```

## Examples

### Passing Example

All workflows have explicit permissions, no injectable expressions, and secure checkout configuration:

```json
{
  "ci": {
    "security": {
      "source": { "tool": "gha-security", "version": "0.1.0", "integration": "code" },
      "injectable_expressions": [],
      "dangerous_checkouts": [],
      "permissions_missing": [],
      "write_all_permissions": [],
      "persist_credentials": [],
      "secrets_inherit": []
    }
  }
}
```

### Failing Example — Script Injection

A workflow uses `github.event.pull_request.title` directly in a `run:` block:

```json
{
  "ci": {
    "security": {
      "source": { "tool": "gha-security", "version": "0.1.0", "integration": "code" },
      "injectable_expressions": [
        {
          "file": ".github/workflows/ci.yml",
          "job": "greet",
          "step": "Echo PR title",
          "expression": "github.event.pull_request.title",
          "context": "run"
        }
      ]
    }
  }
}
```

**Failure message:** `"1 injectable expression(s) found in run blocks — .github/workflows/ci.yml: job 'greet', step 'Echo PR title' uses github.event.pull_request.title"`

### Failing Example — Dangerous Checkout

A `pull_request_target` workflow checks out PR head code:

```json
{
  "ci": {
    "security": {
      "source": { "tool": "gha-security", "version": "0.1.0", "integration": "code" },
      "dangerous_checkouts": [
        {
          "file": ".github/workflows/pr-target.yml",
          "trigger": "pull_request_target",
          "job": "build",
          "step": "Checkout",
          "checkout_ref": "github.event.pull_request.head.sha"
        }
      ]
    }
  }
}
```

**Failure message:** `"1 dangerous checkout(s) found — .github/workflows/pr-target.yml: pull_request_target workflow checks out PR head ref in job 'build'"`

## Remediation

### Script Injection (`no-script-injection`)

Use intermediate environment variables instead of inline expressions:

```yaml
# Bad — injectable
- run: echo "PR: ${{ github.event.pull_request.title }}"

# Good — safe
- run: echo "PR: $PR_TITLE"
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
```

### Dangerous Checkout (`no-dangerous-trigger-checkout`)

Avoid checking out PR head code in `pull_request_target` workflows. If you must, use a two-workflow approach where the trusted workflow runs first:

```yaml
# Use pull_request instead of pull_request_target when possible
on: pull_request
```

### Missing Permissions (`permissions-declared`)

Add an explicit `permissions:` block to every workflow:

```yaml
permissions:
  contents: read
```

### Write-All Permissions (`no-write-all-permissions`)

Replace `permissions: write-all` with specific scopes:

```yaml
# Bad
permissions: write-all

# Good
permissions:
  contents: read
  pull-requests: write
```

### Credential Persistence (`checkout-no-persist-credentials`)

Set `persist-credentials: false` on all checkout steps:

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false
```

### Secrets Inherit (`no-secrets-inherit`)

Pass only the secrets the called workflow needs:

```yaml
# Bad
uses: ./.github/workflows/deploy.yml
secrets: inherit

# Good
uses: ./.github/workflows/deploy.yml
secrets:
  DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
```

