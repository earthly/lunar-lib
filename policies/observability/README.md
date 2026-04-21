# Observability Guardrails

Enforce baseline observability standards for production services: linked monitoring dashboard and configured alert rules.

## Overview

This policy validates that each service has a linked monitoring dashboard and at least one alert rule configured. It reads from the tool-agnostic `.observability` category, so the same checks work whether the data comes from Grafana, Datadog, or another provider.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `dashboard-exists` | Verifies a monitoring dashboard is linked to the service |
| `alerts-configured` | Verifies at least one alert rule is configured |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.observability.dashboard.exists` | boolean | `grafana` collector (or any observability-category collector) |
| `.observability.alerts.configured` | boolean | `grafana` collector |

**Note:** Ensure a collector that writes to the `.observability` category is configured before enabling this policy.

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
    "source": { "tool": "grafana", "integration": "api" },
    "dashboard": { "id": "abc123", "exists": true, "url": "https://grafana.example.com/d/abc123" },
    "alerts": { "configured": true, "count": 5 }
  }
}
```

### Failing Example

```json
{
  "observability": {
    "source": { "tool": "grafana", "integration": "api" },
    "dashboard": { "id": "abc123", "exists": false },
    "alerts": { "configured": false, "count": 0 }
  }
}
```

**Failure message (dashboard-exists):** `"No monitoring dashboard is linked for this service"`

## Remediation

When this policy fails, you can resolve it by:

1. **dashboard-exists:** Create or link a monitoring dashboard for the service. For Grafana, register the dashboard UID on the component via `lunar catalog component --meta grafana/dashboard-uid <uid>`.
2. **alerts-configured:** Create at least one alert rule scoped to the service's dashboard folder in Grafana (or the equivalent construct in your monitoring tool).
