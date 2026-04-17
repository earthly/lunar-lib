# PagerDuty Collector

Collect on-call schedule and escalation data from the PagerDuty API.

## Overview

This collector queries the PagerDuty REST API on a daily cron schedule to
gather on-call schedule, escalation policy, and service data. It discovers
the PagerDuty service ID from the component's `pagerduty/service-id` meta
annotation (set via `lunar catalog component --meta pagerduty/service-id
<id>`, typically by a company-specific cataloger) or accepts an explicit
`service_id` input for static org-wide cases. Results are written to the
`.oncall` category in a tool-agnostic format, so the same `oncall` policy
works regardless of whether the data comes from PagerDuty, OpsGenie, or
another provider.

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
    # with:
    #   service_id: "PXXXXXX"  # Optional — falls back to catalog meta annotation
```

Required secrets:
- `PAGERDUTY_API_KEY` — PagerDuty REST API key (read-only, with service and oncall scopes)

### Service ID discovery

The collector resolves the PagerDuty service ID in this order:

1. **Catalog meta annotation** — reads `pagerduty/service-id` from the component's lunar catalog meta. Set via `lunar catalog component --meta pagerduty/service-id <id>`, typically invoked by a company-specific cataloger that knows which components map to which PagerDuty services. This is the recommended approach for orgs where each component has its own service.
2. **Explicit `service_id` input** — set in `lunar-config.yml` for static org-wide configurations, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own service ID).
3. **Neither found** — the collector exits cleanly with no data written.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `service_id` | *(empty — falls back to catalog meta)* | PagerDuty service ID (e.g. `PXXXXXX`). Optional if `pagerduty/service-id` meta annotation is set. |
| `pagerduty_base_url` | `https://api.pagerduty.com` | PagerDuty API base URL |
