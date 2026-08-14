# PagerDuty Collector

Collect on-call schedule and escalation data from the PagerDuty API.

## Overview

This collector queries the PagerDuty REST API to gather on-call schedule,
escalation policy, and service data, writing normalized results to the
`.oncall` category in a tool-agnostic format so the same `oncall` policy works
for PagerDuty, OpsGenie, or any other provider. It ships two trigger variants
that run the same query and write the same data — `oncall` (code hook, on PRs
and the default branch) and `oncall-cron` (daily cron); pick whichever fits
(see Collectors below). The service ID is discovered from the component's
`pagerduty/service-id` meta annotation, an explicit `service_id` input, or —
with `backstage_discovery` enabled — the repo's `catalog-info.yaml` annotation.

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

This integration provides the following collectors — use `include` to select
one (or include both to collect on both triggers). Both run the same query and
write the same `.oncall` data; they differ only in **when** they run.

| Collector | Description |
|-----------|-------------|
| `oncall` | Code hook — queries PagerDuty on pushes to PRs and the default branch, so the on-call guardrail is evaluated as part of a commit/PR check |
| `oncall-cron` | Cron hook — queries PagerDuty daily (04:00 UTC, staggered off the 02:00/03:00 scheduled jobs) and refreshes `.oncall` so the data stays current as schedules rotate, independent of code changes |

## Installation

Add to your `lunar-config.yml` (use `include` to pick a trigger variant):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/pagerduty@v1.0.0
    include: [oncall]          # code hook (PRs + default branch); use [oncall-cron] for the daily-cron variant
    on: ["domain:your-domain"]
    # with:
    #   service_id: "PXXXXXX"  # Optional — falls back to catalog meta annotation
```

Secrets:
- `PAGERDUTY_API_KEY` — PagerDuty REST API key (read-only, with service and oncall scopes). Required.

(No GitHub token is needed for `backstage_discovery` — `oncall` (code) runs on a fresh checkout and `oncall-cron` sets `clone-code: true`, so either way the collector reads `catalog-info.yaml` from the runner's checkout, not the API.)

### Service ID discovery

The collector resolves the PagerDuty service ID in this order:

1. **Catalog meta annotation** — reads `pagerduty/service-id` from the component's lunar catalog meta. Set via `lunar catalog component --meta pagerduty/service-id <id>`, typically invoked by a company-specific cataloger that knows which components map to which PagerDuty services. This is the recommended approach for orgs where each component has its own service.
2. **Explicit `service_id` input** — set in `lunar-config.yml` for static org-wide configurations, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own service ID).
3. **Backstage discovery (opt-in)** — when `backstage_discovery: "true"`, the collector reads the component's own `catalog-info.yaml` from the runner's checkout (the `oncall` code hook clones automatically; `oncall-cron` sets `clone-code: true`) and takes the service ID directly from its annotations (`backstage_annotations`, default `pagerduty.com/service-id,pagerduty/service-id`). This lets the `oncall` guardrails work off the [standard PagerDuty Backstage annotation](https://support.pagerduty.com/main/docs/backstage-integration-guide) with no cataloger and no component meta — useful today, while component-meta support (`LUNAR_COMPONENT_META`) is still landing in the hub. No GitHub token needed: it reads the runner's checkout, not the API.

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
| `backstage_discovery` | `"false"` | When `"true"`, discover the service ID from the component's checked-out `catalog-info.yaml` annotations if meta/`service_id` don't provide one. No token needed (uses the runner's `clone-code` checkout). |
| `backstage_annotations` | `pagerduty.com/service-id,pagerduty/service-id` | Comma-separated annotation keys to read the service ID from (first non-empty wins), tried in order. Only used when `backstage_discovery` is `"true"`. |
| `backstage_catalog_paths` | `catalog-info.yaml,catalog-info.yml` | Comma-separated catalog-info file paths to try in the checked-out repo (first match wins). Only used when `backstage_discovery` is `"true"`. |
