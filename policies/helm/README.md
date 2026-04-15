# Helm Guardrails

Enforces Helm chart best practices for production-ready charts.

## Overview

This policy validates Helm charts against best practices including lint validation, semantic versioning, values schema presence, and dependency version pinning. It helps ensure your Helm charts are well-structured, properly versioned, and safe to deploy.

## Policies

This policy provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `lint-passed` | Validates charts pass helm lint | Chart has template or YAML errors |
| `version-semver` | Checks chart versions follow semver | Chart version is not valid semver |
| `values-schema` | Requires values.schema.json | Chart missing values input validation |
| `dependencies-pinned` | Checks dependency version constraints | Dependency using `*` or empty version |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.helm.charts[]` | array | `helm` collector |
| `.helm.charts[].lint_passed` | boolean | `helm` collector |
| `.helm.charts[].lint_errors` | array | `helm` collector |
| `.helm.charts[].version` | string | `helm` collector |
| `.helm.charts[].version_is_semver` | boolean | `helm` collector |
| `.helm.charts[].has_values_schema` | boolean | `helm` collector |
| `.helm.charts[].dependencies[]` | array | `helm` collector |

**Note:** Ensure the `helm` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/helm@v1.0.0
    on: [kubernetes, helm]

policies:
  - uses: github://earthly/lunar-lib/policies/helm@v1.0.0
    on: [kubernetes, helm]
    enforcement: report-pr
    # include: [lint-passed, version-semver]  # Only run specific checks
```

## Examples

### Passing Example

A compliant chart with proper versioning, lint results, schema, and pinned dependencies:

```json
{
  "helm": {
    "charts": [
      {
        "path": "charts/api",
        "name": "api",
        "version": "1.2.3",
        "version_is_semver": true,
        "lint_passed": true,
        "lint_errors": [],
        "has_values_schema": true,
        "schema_path": "charts/api/values.schema.json",
        "dependencies": [
          {
            "name": "postgresql",
            "version": "~11.9.0",
            "is_pinned": true
          }
        ]
      }
    ]
  }
}
```

### Failing Example

A chart with lint errors, non-semver version, no schema, and unpinned dependencies:

```json
{
  "helm": {
    "charts": [
      {
        "path": "charts/app",
        "name": "app",
        "version": "latest",
        "version_is_semver": false,
        "lint_passed": false,
        "lint_errors": ["templates/deployment.yaml: error converting YAML to JSON"],
        "has_values_schema": false,
        "dependencies": [
          {
            "name": "redis",
            "version": "*",
            "is_pinned": false
          }
        ]
      }
    ]
  }
}
```

**Failure messages:**
- `charts/app: Chart 'app' failed helm lint: templates/deployment.yaml: error converting YAML to JSON`
- `charts/app: Chart 'app' version 'latest' is not valid semver`
- `charts/app: Chart 'app' missing values.schema.json`
- `charts/app: Dependency 'redis' version '*' is not pinned`

## Remediation

When this policy fails, resolve it by:

1. **For `lint-passed` failures:** Run `helm lint <chart-dir>` locally and fix reported errors
2. **For `version-semver` failures:** Update the `version` field in Chart.yaml to follow semver (e.g., `1.0.0`)
3. **For `values-schema` failures:** Add a `values.schema.json` file to validate chart values at install time
4. **For `dependencies-pinned` failures:** Replace `*` or empty versions in Chart.yaml dependencies with version constraints (e.g., `~1.2.0`, `^2.0.0`, `>=1.0.0 <2.0.0`)
