# Helm Collector

Parse Helm charts and collect chart metadata, lint results, and dependency information.

## Overview

This collector finds all Helm charts in a repository (directories containing `Chart.yaml`) and extracts structured metadata. It runs `helm lint` on each chart, parses version information, checks for a `values.schema.json` file, and enumerates chart dependencies with their version constraints. The collector outputs normalized data under `.k8s.helm` for policy evaluation.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.k8s.helm.source` | object | Tool metadata (tool name and version) |
| `.k8s.helm.charts[]` | array | Discovered Helm charts with metadata |
| `.k8s.helm.charts[].path` | string | Chart directory path |
| `.k8s.helm.charts[].name` | string | Chart name from Chart.yaml |
| `.k8s.helm.charts[].version` | string | Chart version |
| `.k8s.helm.charts[].version_is_semver` | boolean | Whether version follows semver |
| `.k8s.helm.charts[].lint_passed` | boolean | Whether helm lint passed |
| `.k8s.helm.charts[].lint_errors` | array | Lint error messages (empty if passed) |
| `.k8s.helm.charts[].app_version` | string | App version from Chart.yaml (appVersion field) |
| `.k8s.helm.charts[].has_values_schema` | boolean | Whether values.schema.json exists |
| `.k8s.helm.charts[].schema_path` | string | Path to values schema file |
| `.k8s.helm.charts[].dependencies[]` | array | Chart dependencies from Chart.yaml |
| `.k8s.helm.charts[].dependencies[].name` | string | Dependency name |
| `.k8s.helm.charts[].dependencies[].version` | string | Version constraint |
| `.k8s.helm.charts[].dependencies[].repository` | string | Repository URL for the dependency |
| `.k8s.helm.charts[].dependencies[].is_pinned` | boolean | Whether version is constrained (not `*` or empty) |
| `.k8s.helm.cicd.cmds[]` | array | Helm commands executed in CI |
| `.k8s.helm.cicd.source` | object | CI integration metadata |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `charts` | Collects Helm chart metadata, lint results, schema presence, and dependencies |
| `cicd` | Tracks helm commands executed in CI (install, upgrade, template, package) |

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
