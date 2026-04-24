# Datadog Collector

Collect dashboard, monitor, and SLO data from Datadog via the API, and discover Datadog-as-code JSON files committed in the component repository.

## Overview

This plugin provides two sub-collectors. The `service` sub-collector queries the Datadog REST API for monitors, dashboard, and SLOs tagged with the component's service. The `repo-files` sub-collector walks the repo for Datadog-as-code JSON files (dashboards and monitor definitions) and captures their raw contents. All data lands under the tool-agnostic `.observability` category, so the shared `observability` policy works regardless of whether the data came from Datadog, Grafana, or another provider.

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
| `.observability.native.datadog.repo_dashboards` | array | Raw JSON of each Datadog dashboard file discovered in the repo, with its path |
| `.observability.native.datadog.repo_monitors` | array | Raw JSON of each Datadog monitor file discovered in the repo, with its path |

## Collectors

This plugin provides the following sub-collectors:

| Collector | Description |
|-----------|-------------|
| `service` | Queries Datadog API for monitors (by service tag), dashboard (by UUID), and SLOs (by service tag) (code hook) |
| `repo-files` | Discovers Datadog dashboard and monitor JSON files in the repo by content fingerprint (code hook) |

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
      # find_command: "find ./datadog -type f -name '*.json'"  # Optional, narrows repo scan
```

Required secrets:
- `DATADOG_API_KEY` — Datadog API key (Organization Settings → API Keys)
- `DATADOG_APP_KEY` — Datadog application key (Organization Settings → Application Keys). Required for monitor, dashboard, and SLO reads — these endpoints require both the API key and the application key.

**Application key scopes.** Modern Datadog application keys are scoped — if you pick "Custom Scopes" at creation time, select at minimum the scopes listed below, otherwise the API returns 403 for the matching endpoints. If you pick "All Scopes" at creation time no further action is needed, but least-privilege is preferred:

| Scope | Used by | Datadog endpoint |
|-------|---------|------------------|
| `monitors_read` | `service` sub-collector | `GET /api/v1/monitor` |
| `dashboards_read` | `service` sub-collector | `GET /api/v1/dashboard/{id}` |
| `slos_read` | `service` sub-collector | `GET /api/v1/slo` |

The `repo-files` sub-collector does not call the Datadog API and is unaffected by application-key scoping.

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

### Repo file discovery (the `repo-files` sub-collector)

The `repo-files` sub-collector walks the cloned component repo and identifies Datadog-as-code JSON files by content fingerprint:

- **Dashboards** — any `.json` file whose top-level object contains both a `widgets` array and a `layout_type` field (string, typically `ordered` or `free`). This is the shape produced by Datadog's UI JSON export and by the `datadog_dashboard_json` Terraform resource.
- **Monitors** — any `.json` file whose top-level object contains `type` (string, e.g. `metric alert`, `query alert`, `service check`, `log alert`), `query` (string), and `name` (string). This is the shape of Datadog's Monitor API payload and what the `datadog-ci` and Datadog Terraform provider produce.

By default the full repo is walked. Set the `find_command` input to narrow the search to a specific directory (for example `find ./datadog -type f -name '*.json'`). This mirrors the pattern used by the Grafana collector's `repo-dashboards` sub-collector. Files that do not match either fingerprint are silently skipped. If no dashboards or monitors are found, nothing is written.

This sub-collector does not write to normalized `.observability.dashboard` / `.observability.alerts` paths — the API sub-collector owns those. `.observability.native.datadog.repo_*` is intentionally raw — users write their own policies against the dashboard/monitor JSON if they care about widget types, query shapes, notification targets, etc.

### Notes on behavior

- Both sub-collectors run on the `code` hook, so they fire on each push rather than a schedule. This matches the Grafana collector's pattern — the clone is cheap and keeps the data fresh on every change. The `service` sub-collector does not actually read from the repo, but the clone is cheap and keeps the hook model consistent across the plugin.
- When Datadog API credentials are missing or the service name is not resolved, the `service` sub-collector exits 0 with a stderr message — no error, no partial data. The `repo-files` sub-collector works independently of API credentials.
- Example Component JSON is defined in `lunar-collector.yml` under `example_component_json`.
