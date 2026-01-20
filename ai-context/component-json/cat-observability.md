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
      "exists": true,
      "url": "https://grafana.example.com/d/abc123"
    },
    "alerts": {
      "configured": true,
      "count": 5
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
- `.observability.summary.golden_signals_complete` — All 4 signals
