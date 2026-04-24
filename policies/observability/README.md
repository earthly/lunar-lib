# Observability Guardrails

Enforce baseline observability standards for production services: linked monitoring dashboard, configured alert rules, and defined Service Level Objectives.

## Overview

This policy validates that each service has a linked monitoring dashboard, at least one alert rule configured, and at least one SLO defined. It reads from the tool-agnostic `.observability` category, so the same checks work whether the data comes from Grafana, Datadog, or another provider. For Datadog, "monitors" normalize to `.observability.alerts` and are covered by `alerts-configured`.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `dashboard-exists` | Verifies a monitoring dashboard is linked to the service |
| `alerts-configured` | Verifies at least one alert rule (Datadog monitor, Grafana alert, etc.) is configured |
| `slo-defined` | Verifies at least one Service Level Objective is defined for the service |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.observability.dashboard.exists` | boolean | `grafana`, `datadog` (or any observability-category collector) |
| `.observability.alerts.configured` | boolean | `grafana`, `datadog` |
| `.observability.slo.defined` | boolean | `datadog` (collectors that support SLOs) |

**Note:** Ensure a collector that writes to the `.observability` category is configured before enabling this policy. The `slo-defined` check requires a collector that populates `.observability.slo` (e.g. `datadog`); in Grafana-only deployments it will skip unless SLO data is provided separately.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/observability@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [dashboard-exists]  # Only run specific checks
```

## Examples

### Passing Example

```json
{
  "observability": {
    "source": { "tool": "datadog", "integration": "api" },
    "dashboard": { "id": "abc-123-def", "exists": true, "url": "https://app.datadoghq.com/dashboard/abc-123-def" },
    "alerts": { "configured": true, "count": 7 },
    "slo": { "defined": true, "count": 2, "has_error_budget": true }
  }
}
```

### Failing Example

```json
{
  "observability": {
    "source": { "tool": "datadog", "integration": "api" },
    "dashboard": { "id": "abc-123-def", "exists": false },
    "alerts": { "configured": false, "count": 0 },
    "slo": { "defined": false, "count": 0 }
  }
}
```

**Failure message (dashboard-exists):** `"No monitoring dashboard is linked for this service"`

## Remediation

When this policy fails, you can resolve it by:

1. **dashboard-exists:** Create or link a monitoring dashboard for the service. For Grafana, register the dashboard UID on the component via `lunar catalog component --meta grafana/dashboard-uid <uid>`. For Datadog, set `datadog/dashboard-id` via `lunar catalog component --meta datadog/dashboard-id <uuid>`.
2. **alerts-configured:** Create at least one alert rule (Grafana alert in the service's dashboard folder, Datadog monitor tagged with the service, or the equivalent construct in your monitoring tool).
3. **slo-defined:** Create at least one Service Level Objective for the service (Datadog SLO tagged with the service, Grafana SLO, or the equivalent in your SLO platform).
