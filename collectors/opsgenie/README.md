# OpsGenie Collector

Collect on-call schedule and escalation data from the OpsGenie API.

## Overview

This collector queries the OpsGenie REST API on a daily cron schedule to
gather on-call schedule, escalation policy, and team data. It discovers
the OpsGenie team ID from the component's `opsgenie/team-id` meta
annotation (set via `lunar catalog component --meta opsgenie/team-id
<id>`, typically by a company-specific cataloger) or accepts an explicit
`team_id` input for static org-wide cases. Results are written to the
`.oncall` category in a tool-agnostic format, so the same `oncall` policy
works regardless of whether the data comes from OpsGenie, PagerDuty, or
another provider.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.oncall.source` | object | Tool and integration metadata |
| `.oncall.service` | object | OpsGenie team ID, name, and status |
| `.oncall.schedule` | object | On-call schedule: exists flag, participant count, rotation type |
| `.oncall.escalation` | object | Escalation policy: exists flag, level count, policy name |
| `.oncall.summary` | object | Summary flags for quick policy evaluation |
| `.oncall.native.opsgenie` | object | Raw OpsGenie API responses |

## Collectors

This integration provides the following collectors:

| Collector | Description |
|-----------|-------------|
| `oncall` | Fetches team, schedule, and escalation data from OpsGenie API |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/opsgenie@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   team_id: "4513b7ea-3b91-438f-b7e4-e3e54af9147c"  # Optional — falls back to catalog meta annotation
    #   opsgenie_base_url: "https://api.eu.opsgenie.com"  # For EU-region accounts
```

Required secrets:
- `OPSGENIE_API_KEY` — OpsGenie REST API key (read-only, with read access to teams, schedules, and escalations)

### Team ID discovery

The collector resolves the OpsGenie team ID in this order:

1. **Catalog meta annotation** — reads `opsgenie/team-id` from the component's lunar catalog meta. Set via `lunar catalog component --meta opsgenie/team-id <id>`, typically invoked by a company-specific cataloger that knows which components map to which OpsGenie teams. This is the recommended approach for orgs where each component owns its own team.
2. **Explicit `team_id` input** — set in `lunar-config.yml` for static org-wide configurations, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own team ID).
3. **Neither found** — the collector exits cleanly with no data written.

### EU vs US accounts

OpsGenie operates separate US and EU instances. Set `opsgenie_base_url`
to `https://api.eu.opsgenie.com` if your OpsGenie account is hosted in
the EU region. The default `https://api.opsgenie.com` targets the US
instance.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `team_id` | *(empty — falls back to catalog meta)* | OpsGenie team UUID. Optional if `opsgenie/team-id` meta annotation is set. |
| `opsgenie_base_url` | `https://api.opsgenie.com` | OpsGenie API base URL (use `https://api.eu.opsgenie.com` for EU accounts) |

### Team-centric data model

OpsGenie organises on-call around teams; each team owns one or more schedules and one or more escalation policies. This collector picks the first schedule and first escalation owned by the configured team to populate the normalized `.oncall.schedule` and `.oncall.escalation` paths. Teams with multiple schedules or escalations (e.g. business-hours vs after-hours) will only surface one — the others remain available under `.oncall.native.opsgenie` for advanced policies.

The `policies/oncall` plugin reads from `.oncall.*` and works against either OpsGenie or PagerDuty data — pick whichever collector matches your tooling.
