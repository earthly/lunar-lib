# Container Scan Guardrails

Enforces container image vulnerability scanning standards for container security.

## Overview

This policy validates that container scanning is configured and enforces vulnerability thresholds for container images. It works with any container scanner that writes to the normalized `.container_scan` path in the Component JSON (Trivy, Grype, Snyk Container, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies container scanning ran | No scanner has written to `.container_scan` |
| `max-severity` | No findings at or above severity threshold | Findings found at configured severity or higher |
| `max-total` | Total vulnerabilities under threshold | Total count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.container_scan` | object | Any container scanner collector (Trivy, Grype, etc.) |
| `.container_scan.vulnerabilities.critical` | number | Container scanner collector |
| `.container_scan.vulnerabilities.high` | number | Container scanner collector |
| `.container_scan.vulnerabilities.total` | number | Container scanner collector |
| `.container_scan.summary.has_critical` | boolean | Container scanner collector (preferred) |
| `.container_scan.summary.has_high` | boolean | Container scanner collector (preferred) |

**Note:** If collectors don't yet write vulnerability counts, the `max-severity` and `max-total` checks will fail. Use `include: [executed]` to only verify the scanner ran until collectors are enhanced.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/container-scan@main
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
  "container_scan": {
    "source": { "tool": "trivy", "integration": "cicd" },
    "vulnerabilities": { "critical": 0, "high": 0, "medium": 5, "total": 12 },
    "summary": { "has_critical": false, "has_high": false }
  }
}
```

### Failing Example

```json
{
  "container_scan": {
    "source": { "tool": "trivy", "integration": "cicd" },
    "vulnerabilities": { "critical": 3, "high": 8, "medium": 15, "total": 40 },
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No container scan data found. Ensure a scanner (Trivy, Grype, etc.) is configured."
- `max-severity`: "Critical container vulnerabilities detected (3 found)"
- `max-total`: "Total container vulnerability findings (40) exceeds threshold (10)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure a container scanner (Trivy, Grype, Snyk Container) in your CI pipeline.
2. **`max-severity` failure:** Review and remediate flagged vulnerabilities by updating base images or using vulnerability suppression for accepted risks.
3. **`max-total` failure:** Reduce total vulnerability count by updating base images and dependencies.
