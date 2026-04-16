# Backstage Collector

Parses and lints Backstage `catalog-info.yaml` files to collect service catalog metadata.

## Overview

This collector scans the repository for a Backstage catalog definition file (`catalog-info.yaml` or `catalog-info.yml`), parses it, and lints it for schema/syntax issues. It extracts entity metadata, annotations, API declarations, and dependencies. Data is written to the `.catalog` Component JSON category, enabling backstage policy enforcement. The search paths are configurable via the `paths` input.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.catalog.exists` | boolean | Whether a catalog-info file was found |
| `.catalog.valid` | boolean | Whether the catalog-info file passed lint/schema checks |
| `.catalog.errors[]` | array | Lint findings (each with `line`, `message`, `severity`) |
| `.catalog.source` | object | Source metadata (`tool`, `file` path) |
| `.catalog.entity` | object | Entity metadata (`name`, `type`, `description`, `owner`, `system`, `lifecycle`, `tags`) |
| `.catalog.annotations` | object | Normalized annotations (`pagerduty_service`, `grafana_dashboard`, `runbook`, `slack_channel`) |
| `.catalog.apis` | object | API declarations (`provides[]`, `consumes[]`) |
| `.catalog.dependencies` | array | Declared runtime dependencies |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `catalog-info` | code | Parses and lints `catalog-info.yaml`; writes parsed metadata and lint results |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/backstage@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   paths: "catalog-info.yaml,catalog-info.yml"  # Customize search paths
```
