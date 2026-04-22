# Datadog Collector

Collect dashboard, monitor, and SLO data from Datadog via the API.

## Overview

This plugin provides one sub-collector, `service`, that queries the Datadog REST API on every code event for the monitors, dashboard, and SLOs linked to each component. Monitors and SLOs are discovered by filtering on the component's Datadog service tag (`service:<name>`), resolved from the component's `datadog/service-name` meta annotation or the explicit `service_name` input. A dashboard UUID, when provided via meta or input, is fetched directly — Datadog dashboards are not universally tagged with `service:`, so the mapping must be explicit.

All data lands under the tool-agnostic `.observability` category, so the shared `observability` policy works regardless of whether the data comes from Datadog, Grafana, or another provider.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.observability.source` | object | Tool and integration metadata |
| `.observability.dashboard.id` | string | Tool-agnostic dashboard identifier (for Datadog, the dashboard UUID; set even when the dashboard no longer exists) |
| `.observability.dashboard.exists` | boolean | Whether the linked Datadog dashboard exists |
| `.observability.dashboard.url` | string | Direct URL to the dashboard |
| `.observability.alerts.configured` | boolean | Whether any Datadog monitors are configured for the service tag |
| `.observability.alerts.count` | number | Number of Datadog monitors scoped to the service tag |
| `.observability.slo.defined` | boolean | Whether any SLOs are configured for the service tag |
| `.observability.slo.count` | number | Number of SLOs scoped to the service tag |
| `.observability.slo.has_error_budget` | boolean | Whether at least one SLO defines an error budget (target below 100% or explicit warning threshold) |
| `.observability.native.datadog.api` | object | Raw Datadog API responses (monitors, dashboard, slos) plus the resolved service tag |

## Collectors

This plugin provides the following sub-collectors:

| Collector | Description |
|-----------|-------------|
| `service` | Queries Datadog API for monitors (by service tag), dashboard (by UUID), and SLOs (by service tag) (code hook) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/datadog@v1.0.0
    on: ["domain:your-domain"]
    with:
      datadog_site: "datadoghq.com"
      # service_name: "payment-api"   # Optional fallback if catalog meta isn't set
      # dashboard_id: "abc-123-def"   # Optional dashboard UUID
```

Required secrets:
- `DATADOG_API_KEY` — Datadog API key (Organization Settings → API Keys)
- `DATADOG_APP_KEY` — Datadog application key (Organization Settings → Application Keys). Required for monitor, dashboard, and SLO reads — these endpoints require both the API key and the application key.

### Service discovery

The `service` sub-collector resolves the component's Datadog service tag in this order:

1. **Catalog meta annotation** — reads `datadog/service-name` from the component's lunar catalog meta. Set via `lunar catalog component --meta datadog/service-name <name>`, typically by a company-specific cataloger that knows which components map to which Datadog services. This is the recommended approach.
2. **`service_name` input** — explicit value passed via `with: service_name: <name>` in `lunar-config.yml`. Useful for static cases or for orgs that don't run a cataloger.
3. If neither is set, the sub-collector exits cleanly with no data written.

Monitors and SLOs are listed via the Datadog API and filtered on `service:<name>` tag. `.observability.alerts.count` and `.observability.slo.count` reflect the number of matching resources.

### Dashboard discovery

Datadog dashboards are not universally tagged with `service:`, so the dashboard must be mapped explicitly:

1. **Catalog meta annotation** — `datadog/dashboard-id` set via `lunar catalog component --meta datadog/dashboard-id <uuid>`.
2. **`dashboard_id` input** — explicit value passed via `with: dashboard_id: <uuid>`.
3. If neither is set, dashboard data is not collected (monitors and SLOs still run).

When the UUID resolves but the dashboard does not exist in Datadog, `.observability.dashboard.exists=false` is written so policies can flag the stale link. The UID is always written to `.observability.dashboard.id` so the link is visible in the component JSON even when the dashboard is missing.

### Datadog site support

The `datadog_site` input selects which Datadog region to call. Defaults to `datadoghq.com` (US1). Supported values include `datadoghq.eu` (EU1), `us3.datadoghq.com` (US3), `us5.datadoghq.com` (US5), and `ap1.datadoghq.com` (AP1). The collector builds API URLs as `https://api.<site>` and dashboard links as `https://app.<site>/dashboard/<id>`.

### Notes on behavior

- The sub-collector runs on the `code` hook, so it fires on each push rather than a schedule. This matches the Grafana collector's pattern — the clone is cheap and keeps the data fresh on every change.
- When Datadog API credentials are missing or the service name is not resolved, the collector exits 0 with a stderr message — no error, no partial data.
- Example Component JSON is defined in `lunar-collector.yml` under `example_component_json`.
