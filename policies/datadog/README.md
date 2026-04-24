# Datadog Guardrails

Datadog-specific monitor and SLO policies with no cross-tool equivalent.

## Overview

This plugin enforces Datadog-shaped practices that don't generalize to other observability tools. `monitor-has-pager-target` checks that each monitor's message body routes to a pager via Datadog's `@handle` notification syntax. `slo-burn-rate-alert` checks that each declared SLO has a matching burn-rate alert monitor, preventing fire-and-forget SLOs. Pair this with the tool-agnostic `observability` policy — that one covers presence (dashboard/alerts/SLO exist), this one covers Datadog-native quality checks.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `monitor-has-pager-target` | Verifies every Datadog monitor routes to at least one pager handle |
| `slo-burn-rate-alert` | Verifies every declared SLO has a matching burn-rate alert monitor |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.observability.native.datadog.api.monitors` | array | `datadog` collector (`service` sub-collector) |
| `.observability.native.datadog.api.slos` | array | `datadog` collector (`service` sub-collector) |

**Note:** The `datadog` collector's `service` sub-collector must be enabled to populate this data. Without it, both checks skip cleanly.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/datadog@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [monitor-has-pager-target]   # Run a subset
    with:
      pager_handle_prefixes: "pagerduty,opsgenie"   # Override default list
```

### Configuring pager prefixes

Datadog monitor messages use `@<handle>` syntax to route notifications. The `pager_handle_prefixes` input is a comma-separated list of prefixes that count as a pager — any monitor message containing at least one `@<prefix>-*` handle from this list passes the check. Defaults to `pagerduty,opsgenie,victorops`. Teams that page through other routes (e.g. a custom webhook) can extend the list. `@slack-*` and `@email-*` are intentionally excluded from the defaults since they are not paging channels.

## Examples

### Passing Example

Monitor references a pager handle, SLO has a matching burn-rate alert:

```json
{
  "observability": {
    "native": {
      "datadog": {
        "api": {
          "monitors": [
            {
              "id": 12345,
              "name": "High p99 latency",
              "type": "metric alert",
              "message": "Paging @pagerduty-payments — investigate latency spike.",
              "query": "avg(last_5m):..."
            },
            {
              "id": 67890,
              "name": "Error budget burn (payment-api availability)",
              "type": "slo alert",
              "message": "Budget burn — @pagerduty-payments",
              "query": "burn_rate(\"abc-slo-id\").over(\"7d\") > 2"
            }
          ],
          "slos": [
            { "id": "abc-slo-id", "name": "payment-api availability", "type": "metric", "target": 99.9 }
          ]
        }
      }
    }
  }
}
```

### Failing Example

Monitor has no pager handle, SLO has no burn-rate alert:

```json
{
  "observability": {
    "native": {
      "datadog": {
        "api": {
          "monitors": [
            {
              "id": 12345,
              "name": "High p99 latency",
              "type": "metric alert",
              "message": "Latency spike — check the dashboard.",
              "query": "avg(last_5m):..."
            }
          ],
          "slos": [
            { "id": "abc-slo-id", "name": "payment-api availability", "type": "metric", "target": 99.9 }
          ]
        }
      }
    }
  }
}
```

**Failure messages:**
- `monitor-has-pager-target`: `Monitor 12345 ("High p99 latency") has no pager handle in its message (looked for @pagerduty-*, @opsgenie-*, @victorops-*)`
- `slo-burn-rate-alert`: `SLO abc-slo-id ("payment-api availability") has no matching burn-rate alert monitor`

## Remediation

When this policy fails, you can resolve it by:

1. **monitor-has-pager-target:** Edit the Datadog monitor and include a pager handle in the notification message, e.g. `@pagerduty-<team>`. Configure the handle in Datadog under Integrations → PagerDuty first. If the monitor shouldn't page (e.g. an informational alert), remove it or reclassify it under a different notification policy excluded from this check.
2. **slo-burn-rate-alert:** Create a new monitor in Datadog of type **SLO alert** referencing the SLO ID. Use a burn-rate condition (e.g. `burn_rate("<slo-id>").over("7d") > 2`) and route notifications to the service's pager handle. Datadog's SLO detail page has a "Create alert" shortcut that scaffolds this.
