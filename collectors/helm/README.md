# Helm Collector

Parse Helm charts and collect chart metadata, lint results, and dependency information.

## Overview

This collector finds all Helm charts in a repository (directories containing `Chart.yaml`) and extracts structured metadata. It runs `helm lint` on each chart, parses version information, checks for a `values.schema.json` file, and enumerates chart dependencies with their version constraints. The collector outputs normalized data under `.helm` for policy evaluation.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.helm.source` | object | Tool metadata (tool name and version) |
| `.helm.charts[]` | array | Discovered Helm charts with metadata |
| `.helm.charts[].path` | string | Chart directory path |
| `.helm.charts[].name` | string | Chart name from Chart.yaml |
| `.helm.charts[].version` | string | Chart version |
| `.helm.charts[].version_is_semver` | boolean | Whether version follows semver |
| `.helm.charts[].lint_passed` | boolean | Whether helm lint passed |
| `.helm.charts[].lint_errors` | array | Lint error messages (empty if passed) |
| `.helm.charts[].has_values_schema` | boolean | Whether values.schema.json exists |
| `.helm.charts[].schema_path` | string | Path to values schema file |
| `.helm.charts[].dependencies[]` | array | Chart dependencies from Chart.yaml |
| `.helm.charts[].dependencies[].name` | string | Dependency name |
| `.helm.charts[].dependencies[].version` | string | Version constraint |
| `.helm.charts[].dependencies[].is_pinned` | boolean | Whether version is constrained (not `*` or empty) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `helm` | Collects Helm chart metadata, lint results, schema presence, and dependencies |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/helm@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [kubernetes, helm]
    # with:
    #   find_command: "find ./charts -name 'Chart.yaml'"  # Custom find command
    #   lint_strict: "true"  # Enable strict lint mode
```
