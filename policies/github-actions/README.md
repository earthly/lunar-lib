# GitHub Actions Security Guardrails

Enforces GitHub Actions security best practices — injection prevention, least-privilege permissions, and credential hygiene.

## Overview

Checks GitHub Actions workflows for six categories of security misconfiguration that have led to real-world supply chain compromises. All checks analyze the parsed workflow data collected by the `github-actions` collector — no separate security collector needed. Skips gracefully when no GitHub Actions workflow data is available (i.e., component has no `.github/workflows/` directory). Complements the general `ci` policy (which covers vendor-agnostic lint and dependency pinning) with GHA-specific security checks. Different from the `sast` policy (which covers application code analysis, not CI configuration).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `no-script-injection` | Flags attacker-controlled `${{ }}` expressions in `run:` blocks and `actions/github-script` `script:` fields |
| `no-dangerous-trigger-checkout` | Flags `pull_request_target` workflows that check out PR head code |
| `permissions-declared` | Flags workflows with no explicit `permissions:` key |
| `no-write-all-permissions` | Flags `permissions: write-all` at workflow or job level |
| `checkout-no-persist-credentials` | Flags `actions/checkout` without `persist-credentials: false` |
| `no-secrets-inherit` | Flags `secrets: inherit` in reusable workflow calls |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.ci.native.github_actions.workflows[]` | array | `github-actions` collector (workflows sub-collector) |

The policy walks the parsed workflow data (triggers, permissions, jobs, steps, run blocks, with parameters) and applies security rules directly. No pre-processed security data needed — the collector just gathers the raw workflow structure.

**Note:** Ensure the `github-actions` collector is configured before enabling this policy.

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/github-actions@main
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/github-actions@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [no-script-injection, permissions-declared]  # Run specific checks only
```

## Examples

### Passing Example

Workflow has explicit permissions, safe env-var indirection for user input, and secure checkout:

```json
{
  "ci": {
    "native": {
      "github_actions": {
        "workflows": [
          {
            "file": ".github/workflows/ci.yml",
            "name": "CI",
            "triggers": ["push", "pull_request"],
            "permissions": { "contents": "read" },
            "jobs": {
              "build": {
                "steps": [
                  {
                    "name": "Checkout",
                    "uses": "actions/checkout@abc123",
                    "with": { "persist-credentials": false }
                  },
                  {
                    "name": "Run tests",
                    "run": "echo \"PR: $PR_TITLE\"",
                    "env": { "PR_TITLE": "${{ github.event.pull_request.title }}" }
                  }
                ]
              }
            }
          }
        ]
      }
    }
  }
}
```

### Failing Example — Script Injection

A workflow uses `github.event.pull_request.title` directly in a `run:` block (not via env var):

```json
{
  "ci": {
    "native": {
      "github_actions": {
        "workflows": [
          {
            "file": ".github/workflows/ci.yml",
            "triggers": ["pull_request"],
            "jobs": {
              "greet": {
                "steps": [
                  {
                    "name": "Echo PR title",
                    "run": "echo \"PR: ${{ github.event.pull_request.title }}\""
                  }
                ]
              }
            }
          }
        ]
      }
    }
  }
}
```

**Failure message:** `"1 injectable expression(s) found — .github/workflows/ci.yml: job 'greet', step 'Echo PR title' uses github.event.pull_request.title in run block"`

### Failing Example — Dangerous Checkout

A `pull_request_target` workflow checks out PR head code:

```json
{
  "ci": {
    "native": {
      "github_actions": {
        "workflows": [
          {
            "file": ".github/workflows/pr-target.yml",
            "triggers": ["pull_request_target"],
            "jobs": {
              "build": {
                "steps": [
                  {
                    "name": "Checkout",
                    "uses": "actions/checkout@v4",
                    "with": { "ref": "${{ github.event.pull_request.head.sha }}" }
                  }
                ]
              }
            }
          }
        ]
      }
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

For `actions/github-script`, use `context` properties instead of template expressions:

```yaml
# Bad — injectable
- uses: actions/github-script@v7
  with:
    script: |
      const title = "${{ github.event.pull_request.title }}";

# Good — safe
- uses: actions/github-script@v7
  with:
    script: |
      const title = context.payload.pull_request.title;
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
