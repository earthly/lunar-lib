# IaC Scan Guardrails

Enforces Infrastructure as Code (IaC) security scanning standards for infrastructure security.

## Overview

This policy validates that IaC scanning is configured and enforces finding thresholds for infrastructure security issues. It works with any IaC scanner that writes to the normalized `.iac_scan` path in the Component JSON (Trivy, Checkov, tfsec, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies IaC scanning ran | No scanner has written to `.iac_scan` |
| `no-critical` | No critical severity findings | Critical infrastructure security issues found |
| `no-high` | No high severity findings | High severity issues found (configurable) |
| `max-total` | Total findings under threshold | Total count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.iac_scan` | object | Any IaC scanner (Trivy, Checkov, etc.) |
| `.iac_scan.findings.critical` | number | IaC scanner |
| `.iac_scan.findings.high` | number | IaC scanner |
| `.iac_scan.findings.total` | number | IaC scanner |
| `.iac_scan.summary.has_critical` | boolean | IaC scanner (preferred) |
| `.iac_scan.summary.has_high` | boolean | IaC scanner (preferred) |

**Note:** If collectors don't yet write finding counts, the `no-critical`, `no-high`, and `max-total` checks will fail. Use `include: [executed]` to only verify the scanner ran until collectors are enhanced.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/iac-scan@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [executed, no-critical]  # Only run specific checks
    # with:
    #   enforce_no_high: "true"
    #   max_total_threshold: "10"
```

## Examples

### Passing Example

```json
{
  "iac_scan": {
    "source": { "tool": "trivy", "integration": "ci" },
    "findings": { "critical": 0, "high": 0, "medium": 3, "total": 8 },
    "summary": { "has_critical": false, "has_high": false }
  }
}
```

### Failing Example

```json
{
  "iac_scan": {
    "source": { "tool": "checkov", "integration": "ci" },
    "findings": { "critical": 2, "high": 4, "medium": 10, "total": 25 },
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No IaC scanning data found. Ensure a scanner (Trivy, Checkov, etc.) is configured."
- `no-critical`: "Critical infrastructure security findings detected"
- `no-high`: "High severity infrastructure security findings detected"
- `max-total`: "Total infrastructure security findings (25) exceeds threshold (10)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure an IaC scanner (Trivy, Checkov, tfsec) in your CI pipeline to scan Terraform, Kubernetes manifests, CloudFormation, etc.
2. **`no-critical`/`no-high` failure:** Remediate infrastructure security issues by following the scanner's guidance, enabling encryption, restricting network access, and using least privilege IAM.
3. **`max-total` failure:** Reduce total finding count by fixing issues or adjusting the threshold if the current level is acceptable.
