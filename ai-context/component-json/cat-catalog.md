# Category: `.catalog`

Service catalog entries. Tool-agnostic structure that works with Backstage, ServiceNow, or custom catalogs.

```json
{
  "catalog": {
    "exists": true,
    "source": {
      "tool": "backstage",
      "file": "catalog-info.yaml"
    },
    "entity": {
      "name": "payment-api",
      "type": "service",
      "description": "Payment processing API",
      "owner": "team-payments",
      "system": "payment-platform",
      "lifecycle": "production",
      "tags": ["payments", "api", "tier1"]
    },
    "annotations": {
      "pagerduty_service": "PXXXXXX",
      "grafana_dashboard": "https://...",
      "runbook": "https://...",
      "slack_channel": "#payments-oncall"
    },
    "apis": {
      "provides": ["payment-api"],
      "consumes": ["user-api", "notification-api"]
    },
    "dependencies": ["database-payments", "cache-redis"]
  }
}
```

## Key Policy Paths

- `.catalog.exists` — Service catalog entry present
- `.catalog.entity.owner` — Owner defined
- `.catalog.entity.lifecycle` — Lifecycle stage
- `.catalog.annotations.pagerduty_service` — PagerDuty linked
- `.catalog.annotations.grafana_dashboard` — Dashboard linked
