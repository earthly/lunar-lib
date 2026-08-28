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
| `.container_scan.vulnerabilities.medium` | number | Container scanner collector |
| `.container_scan.vulnerabilities.low` | number | Container scanner collector |
| `.container_scan.vulnerabilities.total` | number | Container scanner collector |
| `.container_scan.summary.has_critical` | boolean | Container scanner collector (preferred) |
| `.container_scan.summary.has_high` | boolean | Container scanner collector (preferred) |
| `.container_scan.summary.has_medium` | boolean | Container scanner collector (preferred) |
| `.container_scan.summary.has_low` | boolean | Container scanner collector (preferred) |
| `.container_scan.findings[]` | array | Container scanner collector — names the offending packages/CVEs in the `max-severity` failure message and drives `ignore_unfixable` (`cve`, `severity`, `package`, `fix_version`, `fixable`) |

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
      # ignore_unfixable: "true"  # Optional: only fail on findings that have a fix
```

### Only failing on fixable findings

By default `max-severity` fails on every finding at or above `min_severity`,
whether or not a fix exists. That is the right default, but base images routinely
carry criticals that the upstream distro has not fixed — so a release gate on
`critical` can end up permanently closed on findings no change to your own image
can clear. Set `ignore_unfixable: "true"` to narrow the failure to findings that
carry an upgrade target, which is what makes a `block-pr-and-release` gate
practical:

```yaml
    enforcement: block-pr-and-release
    with:
      min_severity: "critical"
      ignore_unfixable: "true"
```

Unfixable findings are **still collected and still visible** in the Component
JSON and the dashboard — the option changes what the check *gates on*, never what
is recorded. It can only turn a failure into a pass: it is applied after the
threshold has already been crossed, so it never creates a failure the default
would not have raised.

Two behaviours worth knowing:

- A finding counts as fixable when the scanner reported a fix version. Trivy and
  Grype can both scan the same image; where they disagree, the one that found a
  fix wins — a fix that exists is actionable.
- If the scanner reported only summary counts and no `.container_scan.findings[]`,
  fixability cannot be evaluated per finding, so the check **fails as it would
  with the option off** and says so in the failure message.
  `.container_scan.summary.all_fixable` is not a substitute: it is a single
  boolean across *all* severities, so it cannot answer whether the in-scope
  findings are fixable.

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
    "findings": [
      { "severity": "critical", "package": "openssl", "cve": "CVE-2026-1234", "fix_version": "3.0.14" },
      { "severity": "high", "package": "libcurl", "cve": "CVE-2026-5678", "fix_version": null }
    ],
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No container scan data found. Ensure a scanner (Trivy, Grype, etc.) is configured."
- `max-severity`: fails with a headline assertion plus one assertion per offending package/CVE (most severe first), the same format the `sca` policy uses — no policy-side cap; the hub truncates the display. When the scanner emits per-finding detail it renders as a nested list under the check:
  ```
  ❌ max-severity
    * Critical container vulnerabilities detected
    * critical: openssl — CVE-2026-1234 (fix: 3.0.14)
    * high: libcurl — CVE-2026-5678 (no fix available)
  ```
  A summary-only scanner (no `.container_scan.findings[]`) falls back to the headline alone (e.g. `Critical container vulnerabilities detected`).
- `max-total`: "Total container vulnerability findings (40) exceeds threshold (10)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure a container scanner (Trivy, Grype, Snyk Container) in your CI pipeline.
2. **`max-severity` failure:** Review and remediate flagged vulnerabilities by updating base images or using vulnerability suppression for accepted risks.
3. **`max-total` failure:** Reduce total vulnerability count by updating base images and dependencies.
