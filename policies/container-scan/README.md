# Container Scan Guardrails

Enforces container image vulnerability scanning standards for image security.

## Overview

This policy validates that container image scanning is configured and enforces vulnerability thresholds. It works with any container scanner that writes to the normalized `.container_scan` path in the Component JSON (Trivy, Grype, Clair, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies container scanning ran | No scanner has written to `.container_scan` |
| `no-critical` | No critical severity vulnerabilities | Critical vulnerabilities found in image |
| `no-high` | No high severity vulnerabilities | High vulnerabilities found (configurable) |
| `max-total` | Total vulnerabilities under threshold | Total count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.container_scan` | object | Any container scanner (Trivy, Grype, etc.) |
| `.container_scan.vulnerabilities.critical` | number | Container scanner |
| `.container_scan.vulnerabilities.high` | number | Container scanner |
| `.container_scan.vulnerabilities.total` | number | Container scanner |
| `.container_scan.summary.has_critical` | boolean | Container scanner (preferred) |
| `.container_scan.summary.has_high` | boolean | Container scanner (preferred) |

**Note:** Ensure a container scanning collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/container-scan@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [executed, no-critical]  # Only run specific checks
    # with:
    #   enforce_no_high: "true"
    #   max_total_threshold: "5"
```

## Examples

### Passing Example

```json
{
  "container_scan": {
    "source": { "tool": "trivy", "integration": "ci" },
    "image": "gcr.io/acme/api:v1.2.3",
    "vulnerabilities": { "critical": 0, "high": 0, "medium": 2, "total": 5 },
    "summary": { "has_critical": false, "has_high": false }
  }
}
```

### Failing Example

```json
{
  "container_scan": {
    "source": { "tool": "trivy", "integration": "ci" },
    "image": "gcr.io/acme/api:v1.2.3",
    "vulnerabilities": { "critical": 1, "high": 2, "medium": 5, "total": 15 },
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No container scanning data found. Ensure a scanner (Trivy, Grype, etc.) is configured."
- `no-critical`: "Critical container vulnerability findings detected"
- `no-high`: "High severity container vulnerability findings detected"
- `max-total`: "Total container vulnerability findings (15) exceeds threshold (5)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure a container scanner (Trivy, Grype, Clair) in your CI pipeline to scan built images.
2. **`no-critical`/`no-high` failure:** Remediate container vulnerabilities by updating base images to newer versions with patches or using distroless/minimal base images.
3. **`max-total` failure:** Reduce total vulnerability count by updating base images and dependencies, or adjust the threshold if acceptable.
