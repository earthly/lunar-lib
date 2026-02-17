# SAST Guardrails

Enforces Static Application Security Testing (SAST) scanning standards for code security.

## Overview

This policy validates that SAST scanning is configured and enforces finding thresholds for code security. It works with any SAST scanner that writes to the normalized `.sast` path in the Component JSON (Semgrep, CodeQL, Snyk Code, SonarQube, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies SAST scanning ran | No scanner has written to `.sast` |
| `max-severity` | No findings at or above severity threshold | Findings found at configured severity or higher |
| `max-total` | Total findings under threshold | Total count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.sast` | object | Any SAST collector (Semgrep, CodeQL, etc.) |
| `.sast.findings.critical` | number | SAST collector |
| `.sast.findings.high` | number | SAST collector |
| `.sast.findings.total` | number | SAST collector |
| `.sast.summary.has_critical` | boolean | SAST collector (preferred) |
| `.sast.summary.has_high` | boolean | SAST collector (preferred) |

**Note:** If collectors don't yet write finding counts, the `max-severity` and `max-total` checks will fail. Use `include: [executed]` to only verify the scanner ran until collectors are enhanced.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sast@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [executed, max-severity]  # Only run specific checks
    with:
      min_severity: "high"        # Fail on critical and high findings
      max_total_threshold: "10"   # Fail if more than 10 total findings
```

## Examples

### Passing Example

```json
{
  "sast": {
    "source": { "tool": "semgrep", "integration": "github_app" },
    "findings": { "critical": 0, "high": 0, "medium": 3, "total": 8 },
    "summary": { "has_critical": false, "has_high": false }
  }
}
```

### Failing Example

```json
{
  "sast": {
    "source": { "tool": "semgrep", "integration": "github_app" },
    "findings": { "critical": 1, "high": 3, "medium": 12, "total": 20 },
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No SAST scanning data found. Ensure a scanner (Semgrep, CodeQL, etc.) is configured."
- `max-severity`: "Critical SAST findings detected (1 found)"
- `max-total`: "Total code findings (20) exceeds threshold (10)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure a SAST scanner (Semgrep, CodeQL, SonarQube) in your CI pipeline or as a GitHub App integration.
2. **`max-severity` failure:** Review and remediate flagged code issues by applying the recommended fixes or marking as false positives in your scanner's configuration.
3. **`max-total` failure:** Reduce total finding count by addressing code issues.
