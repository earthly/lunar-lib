# PagerDuty Collector

Collect on-call schedule and escalation data from the PagerDuty API.

## Overview

This collector queries the PagerDuty REST API on a daily cron schedule to
gather on-call schedule, escalation policy, and service data. It discovers
the PagerDuty service ID from the component's `pagerduty/service-id` meta
annotation (set via `lunar catalog component --meta pagerduty/service-id
<id>`, typically by a company-specific cataloger), accepts an explicit
`service_id` input for static org-wide cases, or — with `backstage_discovery`
enabled — reads the service ID straight from the repo's `catalog-info.yaml`
annotation. Results are written to the
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

Secrets:
- `PAGERDUTY_API_KEY` — PagerDuty REST API key (read-only, with service and oncall scopes). Required.
- `GH_TOKEN` — GitHub token with `Contents: Read` on the component repos. Optional; only needed when `backstage_discovery` is enabled (to fetch `catalog-info.yaml`).

### Service ID discovery

The collector resolves the PagerDuty service ID in this order:

1. **Catalog meta annotation** — reads `pagerduty/service-id` from the component's lunar catalog meta. Set via `lunar catalog component --meta pagerduty/service-id <id>`, typically invoked by a company-specific cataloger that knows which components map to which PagerDuty services. This is the recommended approach for orgs where each component has its own service.
2. **Explicit `service_id` input** — set in `lunar-config.yml` for static org-wide configurations, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own service ID).
3. **Backstage discovery (opt-in)** — when `backstage_discovery: "true"`, the collector fetches the component's own `catalog-info.yaml` via the GitHub Contents API and reads the service ID directly from its annotations (`backstage_annotations`, default `pagerduty.com/service-id,pagerduty/service-id`). This lets the `oncall` guardrails work off the [standard PagerDuty Backstage annotation](https://support.pagerduty.com/main/docs/backstage-integration-guide) with no cataloger and no component meta — useful today, while component-meta support (`LUNAR_COMPONENT_META`) is still landing in the hub. Requires a `GH_TOKEN` secret; component IDs must be `github.com/<owner>/<repo>`.

   ```yaml
   collectors:
     - uses: github://earthly/lunar-lib/collectors/pagerduty@v1.0.0
       on: ["domain:your-domain"]
       with:
         backstage_discovery: "true"
   ```

4. **None found** — the collector exits cleanly with no data written.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `service_id` | *(empty — falls back to catalog meta)* | PagerDuty service ID (e.g. `PXXXXXX`). Optional if `pagerduty/service-id` meta annotation is set. |
| `pagerduty_base_url` | `https://api.pagerduty.com` | PagerDuty API base URL |
| `backstage_discovery` | `"false"` | When `"true"`, discover the service ID from the component's `catalog-info.yaml` annotations if meta/`service_id` don't provide one. Requires the `GH_TOKEN` secret. |
| `backstage_annotations` | `pagerduty.com/service-id,pagerduty/service-id` | Comma-separated annotation keys to read the service ID from (first non-empty wins), tried in order. Only used when `backstage_discovery` is `"true"`. |
| `backstage_catalog_paths` | `catalog-info.yaml,catalog-info.yml` | Comma-separated catalog-info file paths to try in the repo (first match wins). Only used when `backstage_discovery` is `"true"`. |
| `backstage_branch` | *(empty — default branch)* | Git ref to read `catalog-info.yaml` from. Only used when `backstage_discovery` is `"true"`. |
