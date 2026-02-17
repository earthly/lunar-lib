# SCA Guardrails

Enforces Software Composition Analysis (SCA) scanning standards for dependency security.

## Overview

This policy validates that SCA scanning is configured and enforces vulnerability thresholds for dependencies. It works with any SCA scanner that writes to the normalized `.sca` path in the Component JSON (Snyk, Semgrep Supply Chain, Dependabot, Grype, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies SCA scanning ran | No scanner has written to `.sca` |
| `max-severity` | No findings at or above severity threshold | Findings found at configured severity or higher |
| `max-total` | Total vulnerabilities under threshold | Total count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.sca` | object | Any SCA collector (Snyk, Semgrep, etc.) |
| `.sca.vulnerabilities.critical` | number | SCA collector |
| `.sca.vulnerabilities.high` | number | SCA collector |
| `.sca.vulnerabilities.medium` | number | SCA collector |
| `.sca.vulnerabilities.low` | number | SCA collector |
| `.sca.vulnerabilities.total` | number | SCA collector |
| `.sca.summary.has_critical` | boolean | SCA collector (preferred) |
| `.sca.summary.has_high` | boolean | SCA collector (preferred) |
| `.sca.summary.has_medium` | boolean | SCA collector (preferred) |
| `.sca.summary.has_low` | boolean | SCA collector (preferred) |

**Note:** If collectors don't yet write vulnerability counts, the `max-severity` and `max-total` checks will fail. Use `include: [executed]` to only verify the scanner ran until collectors are enhanced.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sca@main
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
  "sca": {
    "source": { "tool": "snyk", "integration": "github_app" },
    "vulnerabilities": { "critical": 0, "high": 0, "medium": 3, "total": 8 },
    "summary": { "has_critical": false, "has_high": false }
  }
}
```

### Failing Example

```json
{
  "sca": {
    "source": { "tool": "snyk", "integration": "github_app" },
    "vulnerabilities": { "critical": 2, "high": 5, "medium": 10, "total": 25 },
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No SCA scanning data found. Ensure a scanner (Snyk, Semgrep, etc.) is configured."
- `max-severity`: "Critical vulnerability findings detected (2 found)"
- `max-total`: "Total vulnerability findings (25) exceeds threshold (10)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure an SCA scanner (Snyk, Semgrep Supply Chain, Dependabot) in your CI pipeline or as a GitHub App integration.
2. **`max-severity` failure:** Review and remediate the flagged vulnerabilities by updating to patched versions or using your scanner's ignore feature for accepted risks.
3. **`max-total` failure:** Reduce total vulnerability count by updating dependencies.
