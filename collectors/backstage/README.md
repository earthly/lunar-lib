# Backstage Collector

Parses and lints Backstage `catalog-info.yaml` files.

## Overview

This collector scans the repository for a Backstage catalog definition file (`catalog-info.yaml` or `catalog-info.yml`), parses it, and lints it for schema/syntax issues. The raw Backstage descriptor (apiVersion, kind, metadata, spec) is written to the `.backstage` Component JSON category as-is — annotations keep their original `backstage.io/` or vendor prefixes. The search paths are configurable via the `paths` input.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.backstage.exists` | boolean | Whether a catalog-info file was found |
| `.backstage.valid` | boolean | Whether the catalog-info file passed lint/schema checks |
| `.backstage.errors[]` | array | Lint findings (each with `line`, `message`, `severity`) |
| `.backstage.path` | string | Relative path to the file that was parsed |
| `.backstage.apiVersion` | string | Backstage API version (e.g. `backstage.io/v1alpha1`) |
| `.backstage.kind` | string | Entity kind (e.g. `Component`, `System`, `API`) |
| `.backstage.metadata` | object | Raw `metadata` block (`name`, `description`, `annotations`, `tags`, etc.) |
| `.backstage.spec` | object | Raw `spec` block (`type`, `owner`, `lifecycle`, `system`, `providesApis`, `consumesApis`, `dependsOn`, etc.) |

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
