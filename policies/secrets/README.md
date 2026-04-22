# Secrets Guardrails

Enforces secret scanning standards and validates that no hardcoded secrets are present in code.

## Overview

This policy validates that secret scanning is configured and enforces that no hardcoded secrets, API keys, or credentials are detected in the codebase. It works with any secret scanner that writes to the normalized `.secrets` path in the Component JSON (Gitleaks, TruffleHog, detect-secrets, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies secret scanning ran | No scanner has written to `.secrets` |
| `no-hardcoded-secrets` | No hardcoded secrets detected | Secrets found in codebase |
| `max-issues` | Issue count under threshold | Issue count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.secrets` | object | Any secret scanner collector (Gitleaks, TruffleHog, etc.) |
| `.secrets.issues[]` | array | Secret scanner collector (empty = clean) |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/secrets@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [executed, no-hardcoded-secrets]  # Only run specific checks
    with:
      max_issues_threshold: "10"  # Default — fails only when issue count exceeds this
```

**Threshold semantics.** `max_issues_threshold` is a remediation lever: `max-issues` fails only when the number of findings *exceeds* the threshold. It must be a positive integer — for zero-tolerance enforcement, enable the `no-hardcoded-secrets` check instead (it's unconditional and has no threshold to misconfigure). The default of `"10"` is a safe starting point for most teams; pair it with `no-hardcoded-secrets` to keep zero-tolerance pressure on new commits while `max-issues` acts as a ceiling for gradual remediation of existing findings.

## Examples

### Passing Example

```json
{
  "secrets": {
    "source": { "tool": "gitleaks", "integration": "code" },
    "issues": []
  }
}
```

### Failing Example

```json
{
  "secrets": {
    "source": { "tool": "gitleaks", "integration": "code" },
    "issues": [
      { "rule": "generic-api-key", "file": "config.py", "line": 10 }
    ]
  }
}
```

**Failure messages:**
- `executed`: "No secret scanning data found. Ensure a scanner (Gitleaks, TruffleHog, etc.) is configured."
- `no-hardcoded-secrets`: "Hardcoded secrets detected in code. Review .secrets.issues for details."
- `max-issues`: "Secret issues (3) exceeds threshold (5)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure a secret scanner (Gitleaks, TruffleHog) in your CI pipeline or use the Gitleaks auto-scan collector.
2. **`no-hardcoded-secrets` failure:** Remove hardcoded secrets from your codebase. Use environment variables, secret managers, or vault systems instead.
3. **`max-issues` failure:** Reduce issue count by remediating detected secrets. Increase the threshold temporarily for gradual remediation.
