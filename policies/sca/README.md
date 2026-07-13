# SCA Guardrails

Enforces Software Composition Analysis (SCA) scanning standards for dependency security.

## Overview

This policy validates that SCA scanning is configured and enforces vulnerability thresholds for dependencies. It works with any SCA scanner that writes to the normalized `.sca` path in the Component JSON (Snyk, Semgrep Supply Chain, Dependabot, Grype, etc.).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies SCA scanning ran | No scanner has written to `.sca` |
| `max-severity` | No findings at or above severity threshold (optionally fires a [webhook](#webhook-alerts) on failure) | Findings found at configured severity or higher |
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
| `.sca.findings[]` | array | SCA collector — used by the optional `max-severity` webhook alert (`cve`, `severity`, `package`, `fix_version`) |

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
      # alert_url: "https://example.com/hook"  # Optional: webhook on max-severity failure
      # alert_timeout_sec: "2"                  # Optional: POST timeout (seconds)
```

### Webhook Alerts

When the `max-severity` check **fails** (a scan turned up findings at or above
`min_severity`) and `alert_url` is set, the check additionally POSTs a webhook
describing those findings — so you can forward CVE findings to a chat channel,
an incident tool, or a custom service the moment a policy fails, without polling
the Hub. Alerting is **opt-in**: leave `alert_url` unset (the default) and no
webhook is ever sent.

The webhook is **additive and best-effort** — it does not replace the failure.
`max-severity` fails exactly as it would without alerting; the POST is a side
effect with a short timeout, and a slow, unreachable, or erroring endpoint
**never changes the check result** (a failing check stays FAILED — it does not
become an ERROR) and never adds unbounded latency.

Enable it by setting `alert_url` in the `with:` block above. If the endpoint
needs authentication, set the `ALERT_AUTH_TOKEN` secret and it is sent as an
`Authorization: Bearer <token>` header. Secrets are scoped per plugin type, so
set it for policies explicitly:

```bash
printf '%s' "$TOKEN" | lunar secret set --scope policy ALERT_AUTH_TOKEN
```

**Payload** — a single `POST` with a JSON body (`Content-Type: application/json`).
The schema is defined in `webhook.py`, which is dependency-free (Python stdlib
only) so other policies can reuse it:

```json
{
  "schema_version": 1,
  "policy": "sca",
  "check": "max-severity",
  "component": "github.com/acme/api",
  "git_sha": "1a2b3c4",
  "pr": 42,
  "min_severity": "high",
  "message": "High vulnerability findings detected: high: golang.org/x/net — CVE-2023-44487 (fix: 0.17.0)",
  "findings": [
    { "id": "CVE-2023-44487", "severity": "high",
      "package": "golang.org/x/net", "fix_version": "0.17.0" }
  ],
  "findings_text": [
    "high: golang.org/x/net — CVE-2023-44487 (fix: 0.17.0)"
  ],
  "run_id": "1a2b3c4",
  "dedupe_key": "9f86d081884c7d65...",
  "timestamp": "2026-06-10T12:34:56Z"
}
```

| Field | Meaning |
|-------|---------|
| `policy` / `check` | the lunar policy and the check that fired (`sca` / `max-severity`) |
| `component` / `git_sha` / `pr` | the component, commit, and PR number (`pr` is `null` when not a PR run) |
| `min_severity` | the configured threshold that was crossed |
| `message` | the same human-readable summary raised on the PR / in the UI |
| `findings` | machine-readable findings at or above `min_severity` (`id`=CVE) |
| `findings_text` | one human-readable line per finding |
| `dedupe_key` | stable hash of component + git sha + finding ids (excludes timestamp) — re-running the same commit yields the same key, so consumers can drop duplicate alerts |

If the collector reports only summary counts (no per-finding `.sca.findings[]`),
`findings` / `findings_text` are empty but `message` is still populated.

**Performance:** the POST happens only on a `max-severity` failure with
`alert_url` set — passing components, sub-threshold components, and
alerting-disabled policies add zero network time. It is one synchronous POST per
evaluation with a configurable timeout (`alert_timeout_sec`, default 2s).

**Requirements:** the POST is an outbound request from the policy runtime, so
the runner must permit network egress to the endpoint (an egress allowlist would
need the endpoint allowlisted). If egress is blocked, the check still fails on
the findings as normal and the delivery failure is logged to stderr.

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
    "vulnerabilities": { "critical": 1, "high": 1, "medium": 10, "total": 25 },
    "findings": [
      { "severity": "critical", "package": "lodash", "version": "4.17.19",
        "cve": "CVE-2021-23337", "fix_version": "4.17.21" },
      { "severity": "high", "package": "axios", "version": "1.3.0",
        "cve": "CVE-2023-45857", "fix_version": null }
    ],
    "summary": { "has_critical": true, "has_high": true }
  }
}
```

**Failure messages:**
- `executed`: "No SCA scanning data found. Ensure a scanner (Snyk, Semgrep, etc.) is configured."
- `max-total`: "Total vulnerability findings (25) exceeds threshold (10)"

`max-severity` lists the offending findings (most severe first) as a sub-list, which renders in the GitHub PR comment as:

> Critical vulnerability findings detected:
> - critical: lodash — CVE-2021-23337 (fix: 4.17.21)
> - high: axios — CVE-2023-45857 (no fix available)

Up to the first 10 are shown, with a `+N more (see More details below for full list)` tail when there are more — pointing readers at the check's **More Details** expander in the PR comment. If the collector reports only summary counts with no per-finding `.sca.findings[]`, the message is just the headline (e.g. `Critical vulnerability findings detected`). The webhook payload's `message` carries the same list in a compact single-line form, tailed with a bare `+N more` (it ships the full structured findings separately).

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure an SCA scanner (Snyk, Semgrep Supply Chain, Dependabot) in your CI pipeline or as a GitHub App integration.
2. **`max-severity` failure:** Review and remediate the flagged vulnerabilities by updating to patched versions or using your scanner's ignore feature for accepted risks.
3. **`max-total` failure:** Reduce total vulnerability count by updating dependencies.
