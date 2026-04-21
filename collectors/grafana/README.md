# Grafana Collector

Collect dashboard and alert rule data from Grafana via the API, and discover Grafana dashboard JSON files committed in the component repository.

## Overview

This plugin provides two sub-collectors. The `dashboard` sub-collector queries the Grafana REST API on a daily cron for the dashboard and alert rules linked to each component via the component's `grafana/dashboard-uid` meta annotation (typically set by a cataloger). The `repo-dashboards` sub-collector walks the component repo looking for Grafana dashboard JSON files by content fingerprint and stashes their raw contents for custom policies. Both write under the tool-agnostic `.observability` category, so the shared `observability` policy works regardless of whether the data comes from Grafana, Datadog, or another provider.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.observability.source` | object | Tool and integration metadata |
| `.observability.dashboard.uid` | string | Resolved Grafana dashboard UID (set even when the dashboard no longer exists) |
| `.observability.dashboard.exists` | boolean | Whether the linked Grafana dashboard exists |
| `.observability.dashboard.url` | string | Direct URL to the dashboard |
| `.observability.alerts.configured` | boolean | Whether any alert rules are configured for the dashboard's folder |
| `.observability.alerts.count` | number | Number of alert rules scoped to the dashboard's folder |
| `.observability.native.grafana.api` | object | Raw Grafana API responses (dashboard + alert rules) |
| `.observability.native.grafana.repo_dashboards` | array | Raw JSON of each Grafana dashboard file discovered in the repo, with its path |

## Collectors

This plugin provides the following sub-collectors:

| Collector | Description |
|-----------|-------------|
| `dashboard` | Queries Grafana API for the dashboard and alert rules linked via the `grafana/dashboard-uid` meta annotation (cron, daily at 02:00 UTC) |
| `repo-dashboards` | Discovers Grafana dashboard JSON files in the repo by content fingerprint (code hook) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/grafana@v1.0.0
    on: ["domain:your-domain"]
    with:
      grafana_base_url: "https://grafana.example.com"
      # find_command: "find ./dashboards -type f -name '*.json'"  # Optional, narrows repo scan
```

Required secrets:
- `GRAFANA_API_KEY` — Grafana API token with `dashboards:read` and `alerting.rules:read` scopes

### Dashboard discovery (the `dashboard` sub-collector)

The `dashboard` sub-collector resolves the component's Grafana dashboard UID **only** from the component's `grafana/dashboard-uid` meta annotation:

1. Set via `lunar catalog component --meta grafana/dashboard-uid <uid>`, typically by a company-specific cataloger that knows which components map to which dashboards.
2. If no meta annotation is set, the sub-collector exits cleanly with no data written.
3. If the meta is set but the dashboard does not exist in Grafana, it writes `.observability.dashboard.exists=false` so policies can flag the stale link.

There is intentionally no explicit `dashboard_uid` input override. Orgs that want file-driven registration can write their own cataloger that reads a repo file and calls `lunar catalog component --meta`.

### Repo dashboard discovery (the `repo-dashboards` sub-collector)

The `repo-dashboards` sub-collector walks the cloned component repo and identifies Grafana dashboard JSON files by content fingerprint: any `.json` file whose top-level object contains both a `schemaVersion` (integer) and a `panels` (array) field is treated as a dashboard and its raw contents are captured.

By default the full repo is walked. Set the `find_command` input to narrow the search to a specific directory (for example `find ./dashboards -type f -name '*.json'`). This mirrors the pattern used by the `k8s` collector for YAML manifest discovery. Files that do not match the fingerprint are silently skipped. If no dashboards are found, nothing is written.

### Notes on behavior

- The `dashboard` sub-collector uses `clone-code: false` — it does not require the repo.
- The `repo-dashboards` sub-collector uses the `code` hook and does require the repo.
- `.observability.native.grafana.repo_dashboards` is intentionally raw — users write their own policies against the dashboard JSON if they care about panel shapes, datasource usage, etc.
- Example Component JSON is defined in `lunar-collector.yml` under `example_component_json`.
