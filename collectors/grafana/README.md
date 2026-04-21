# Grafana Collector

Collect dashboard and alert rule data from Grafana via the API, and discover Grafana dashboard JSON files committed in the component repository.

## Overview

This plugin provides two sub-collectors:

- **`dashboard`** — queries the Grafana REST API on a daily cron for the dashboard and alert rules linked to each component. The link is established via the component's `grafana/dashboard-uid` meta annotation (set by a cataloger). Writes normalized data to `.observability.dashboard` and `.observability.alerts`.
- **`repo-dashboards`** — walks the component repository looking for Grafana dashboard JSON files by content fingerprint, and stores their raw contents under `.observability.native.grafana.repo_dashboards` for users to inspect or build custom policies against.

Both write under the tool-agnostic `.observability` category, so the shared `observability` policy works regardless of whether the data comes from Grafana, Datadog, or another provider.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.observability.source` | object | Tool and integration metadata |
| `.observability.dashboard.exists` | boolean | Whether the linked Grafana dashboard exists |
| `.observability.dashboard.url` | string | Direct URL to the dashboard |
| `.observability.alerts.configured` | boolean | Whether any alert rules are configured for the dashboard's folder |
| `.observability.alerts.count` | number | Number of alert rules scoped to the dashboard's folder |
| `.observability.native.grafana.api.dashboard` | object | Raw Grafana dashboard API response |
| `.observability.native.grafana.api.alert_rules` | array | Raw list of Grafana alert rule objects |
| `.observability.native.grafana.repo_dashboards` | array | Raw JSON of each Grafana dashboard file discovered in the repo, with its path |

## Collectors

This plugin provides the following sub-collectors:

| Collector | Hook | Description |
|-----------|------|-------------|
| `dashboard` | cron (daily at 02:00 UTC) | Queries Grafana API for the dashboard and alert rules linked via `grafana/dashboard-uid` meta |
| `repo-dashboards` | code | Discovers Grafana dashboard JSON files in the repo by content fingerprint |

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

By default the full repo is walked. Set the `find_command` input to narrow the search to a specific directory (for example `find ./dashboards -type f -name '*.json'`). This mirrors the pattern used by the `k8s` collector for YAML manifest discovery.

Files that do not match the fingerprint are silently skipped. If no dashboards are found, nothing is written (no empty arrays).

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `grafana_base_url` | *(empty — dashboard sub-collector skips if empty)* | Grafana API base URL, e.g. `https://grafana.example.com` |
| `find_command` | `find . -type f -name '*.json'` | Command used by `repo-dashboards` to enumerate candidate JSON files (one path per line) |

## Examples

### Dashboard linked, alerts configured

```json
{
  "observability": {
    "source": { "tool": "grafana", "integration": "api" },
    "dashboard": {
      "exists": true,
      "url": "https://grafana.example.com/d/abc123/payment-api"
    },
    "alerts": { "configured": true, "count": 5 }
  }
}
```

### Dashboard UID set but dashboard missing in Grafana

```json
{
  "observability": {
    "source": { "tool": "grafana", "integration": "api" },
    "dashboard": { "exists": false },
    "alerts": { "configured": false, "count": 0 }
  }
}
```

### Repo-discovered dashboards (no API link set)

```json
{
  "observability": {
    "native": {
      "grafana": {
        "repo_dashboards": [
          {
            "path": "dashboards/payment-api.json",
            "dashboard": { "schemaVersion": 39, "title": "Payment API", "panels": [] }
          }
        ]
      }
    }
  }
}
```

## Notes

- The `dashboard` sub-collector runs on cron (daily) with `clone-code: false` — it does not require the repo.
- The `repo-dashboards` sub-collector runs on the `code` hook and does require the repo.
- Both sub-collectors write under `.observability`. The shared `observability` policy evaluates this tool-agnostically, so Datadog (future) can plug into the same normalized paths without the policy needing to change.
- `.observability.native.grafana.repo_dashboards` is intentionally raw — users write their own policies against the dashboard JSON if they care about panel shapes, datasource usage, etc.
