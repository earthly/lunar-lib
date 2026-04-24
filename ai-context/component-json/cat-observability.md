# Category: `.observability`

Monitoring, logging, tracing configuration.

```json
{
  "observability": {
    "logging": {
      "configured": true,
      "structured": true
    },
    "metrics": {
      "configured": true,
      "endpoint": "/metrics",
      "golden_signals": {
        "latency": true,
        "traffic": true,
        "errors": true,
        "saturation": true
      }
    },
    "tracing": {
      "configured": true
    },
    "dashboard": {
      "id": "abc123",
      "exists": true,
      "url": "https://grafana.example.com/d/abc123/payment-api"
    },
    "alerts": {
      "configured": true,
      "count": 5
    },
    "slo": {
      "defined": true,
      "count": 2,
      "has_error_budget": true
    },
    "summary": {
      "has_logging": true,
      "has_metrics": true,
      "has_tracing": true,
      "has_dashboard": true,
      "has_alerts": true,
      "golden_signals_complete": true
    }
  }
}
```

## Key Policy Paths

- `.observability.metrics.golden_signals.<signal>` — Signal monitored
- `.observability.dashboard.exists` — Dashboard configured
- `.observability.alerts.configured` — Alerting enabled
- `.observability.slo.defined` — At least one SLO configured for the service
- `.observability.summary.golden_signals_complete` — All 4 signals
