# IaC Scan Guardrails

Enforces Infrastructure as Code (IaC) security scanning standards for infrastructure security.

## Overview

This policy validates that IaC scanning is configured and enforces finding thresholds for infrastructure code. It works with any IaC scanner that writes to the normalized `.iac_scan` path in the Component JSON (Checkov, tfsec, Trivy config, Snyk IaC, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies IaC scanning ran | No scanner has written to `.iac_scan` |
| `max-severity` | No findings at or above severity threshold | Findings found at configured severity or higher |
| `max-total` | Total findings under threshold | Total count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.iac_scan` | object | Any IaC scanner collector (Checkov, tfsec, etc.) |
| `.iac_scan.findings.critical` | number | IaC scanner collector |
| `.iac_scan.findings.high` | number | IaC scanner collector |
| `.iac_scan.findings.medium` | number | IaC scanner collector |
| `.iac_scan.findings.low` | number | IaC scanner collector |
| `.iac_scan.findings.total` | number | IaC scanner collector |
| `.iac_scan.summary.has_critical` | boolean | IaC scanner collector (preferred) |
| `.iac_scan.summary.has_high` | boolean | IaC scanner collector (preferred) |
| `.iac_scan.summary.has_medium` | boolean | IaC scanner collector (preferred) |
| `.iac_scan.summary.has_low` | boolean | IaC scanner collector (preferred) |

**Note:** If collectors don't yet write finding counts, the `max-severity` and `max-total` checks will fail. Use `include: [executed]` to only verify the scanner ran until collectors are enhanced.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/iac-scan@main
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
  "iac_scan": {
    "source": { "tool": "checkov", "integration": "cicd" },
    "findings": { "critical": 0, "high": 0, "medium": 4, "total": 10 },
    "summary": { "has_critical": false, "has_high": false }
  }
}
```

### Failing Example

```json
{
  "iac_scan": {
    "source": { "tool": "checkov", "integration": "cicd" },
    "findings": { "critical": 2, "high": 6, "medium": 8, "total": 20 },
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No IaC scan data found. Ensure a scanner (Checkov, tfsec, etc.) is configured."
- `max-severity`: "Critical IaC misconfigurations detected (2 found)"
- `max-total`: "Total infrastructure security findings (20) exceeds threshold (10)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure an IaC scanner (Checkov, tfsec, Trivy config) in your CI pipeline.
2. **`max-severity` failure:** Review and remediate flagged misconfigurations by following security best practices or using scanner suppression for accepted risks.
3. **`max-total` failure:** Reduce total finding count by addressing infrastructure issues.
