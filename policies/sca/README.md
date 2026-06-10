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
| `alert` | Optional webhook notifier for findings at or above `min_severity` | Never fails — notifier only (see [Webhook Alerts](#webhook-alerts)) |

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
| `.sca.findings[]` | array | SCA collector — required only by the optional `alert` check (`cve`, `severity`, `package`, `fix_version`) |

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
      # alert_url: "https://example.com/hook"  # Optional: enable webhook alerts
      # alert_timeout: "2"                      # Optional: POST timeout (seconds)
```

### Webhook Alerts

The optional `alert` check posts a webhook to an external endpoint when an SCA
scan turns up findings at or above `min_severity`. It lets you forward CVE
findings to a chat channel, an incident tool, or a custom service without
polling the Hub. Alerting is **opt-in**: leave `alert_url` unset (the default)
and the check skips with no network activity.

Enable it by setting `alert_url` in the `with:` block above. If the endpoint
needs authentication, set the `ALERT_AUTH_TOKEN` secret and it is sent as an
`Authorization: Bearer <token>` header. Secrets are scoped per plugin type, so
set it for policies explicitly:

```bash
printf '%s' "$TOKEN" | lunar secret set --scope policy ALERT_AUTH_TOKEN
```

**Payload** — a single `POST` with a JSON body (`Content-Type: application/json`):

```json
{
  "schema_version": 1,
  "policy": "sca",
  "component": "github.com/acme/api",
  "git_sha": "1a2b3c4",
  "run_id": "1a2b3c4",
  "dedupe_key": "9f86d081884c7d65...",
  "timestamp": "2026-06-10T12:34:56Z",
  "findings": [
    { "id": "CVE-2023-44487", "severity": "high",
      "package": "golang.org/x/net", "fix_version": "0.17.0" }
  ],
  "summary": { "total": 1, "by_severity": { "critical": 0, "high": 1, "medium": 0, "low": 0 } }
}
```

`findings` contains only the entries at or above `min_severity`. The schema is
defined in `webhook.py`, which is dependency-free (Python stdlib only) so other
policies can reuse it.

**Behaviour and guarantees:**

- **Never gates the component.** The `alert` check only ever reports PASS (an
  alert fired) or SKIPPED (alerting disabled, no scan data, or nothing at or
  above the threshold). It has no failure path, so a misconfigured, slow, or
  unreachable endpoint can never block a PR or release. Delivery outcome is
  logged to the policy run's stderr.
- **Bounded latency.** The POST is synchronous with a short timeout
  (`alert_timeout`, default 2s). Cost is incurred only when there is actually
  something to send — a clean component, a sub-threshold component, or a policy
  with alerting disabled all add zero network time.
- **One POST per run.** At most one webhook is sent per policy evaluation,
  carrying all in-scope findings — not one per finding or per check.
- **Idempotent re-runs.** `dedupe_key` is a stable hash of the component, git
  SHA, and the set of finding IDs (the timestamp is excluded). Re-evaluating
  the same commit produces the same key, so consumers can drop duplicates.

**Requirements:** the `alert` check makes an outbound request from the policy
runtime, so the policy runner must permit network egress to the endpoint. Most
policies are pure functions over Component JSON and avoid external calls; this
is a deliberate exception for the alert-on-findings use case. If your
environment blocks policy egress, the check fails safe — it logs the failure
and still passes.

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
