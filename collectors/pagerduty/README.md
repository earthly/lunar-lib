# PagerDuty Collector

Collect on-call schedule and escalation data from the PagerDuty API.

## Overview

This collector queries the PagerDuty REST API on a daily cron schedule to
gather on-call schedule, escalation policy, and service data for a configured
PagerDuty service. Results are written to the `.oncall` category in a
tool-agnostic format, so the same `oncall` policy works regardless of whether
the data comes from PagerDuty, OpsGenie, or another provider.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.oncall.source` | object | Tool and integration metadata |
| `.oncall.service` | object | PagerDuty service ID, name, and status |
| `.oncall.schedule` | object | On-call schedule: exists flag, participant count, rotation type |
| `.oncall.escalation` | object | Escalation policy: exists flag, level count, policy name |
| `.oncall.summary` | object | Summary flags for quick policy evaluation |
| `.oncall.native.pagerduty` | object | Raw PagerDuty API responses |

## Collectors

This integration provides the following collectors:

| Collector | Description |
|-----------|-------------|
| `oncall` | Fetches service, schedule, and escalation data from PagerDuty API |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/pagerduty@v1.0.0
    on: ["domain:your-domain"]
    with:
      service_id: "PXXXXXX"
```

Required secrets:
- `PAGERDUTY_API_KEY` — PagerDuty REST API key (read-only, with service and oncall scopes)

### Optional inputs

| Input | Default | Description |
|-------|---------|-------------|
| `service_id` | *(required)* | PagerDuty service ID to query |
| `pagerduty_base_url` | `https://api.pagerduty.com` | PagerDuty API base URL |
