# Service Catalog Guardrails

Enforce service catalog registration across all components.

## Overview

Tool-agnostic policy that validates components are registered in a service catalog. Works with any collector that writes to the `.catalog` Component JSON category — Backstage, ServiceNow, OpsLevel, or custom catalogs. Use this for organization-wide catalog enforcement regardless of which catalog tool is in use.

## Policies

| Policy | Description |
|--------|-------------|
| `exists` | Validates that a service catalog entry exists for the component |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.catalog.exists` | boolean | Any catalog collector (`backstage`, etc.) |

**Note:** Ensure a catalog collector (e.g., `backstage`) is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/catalog@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
```

## Examples

### Passing Example

```json
{
  "catalog": {
    "exists": true,
    "source": { "tool": "backstage", "file": "catalog-info.yaml" },
    "entity": {
      "name": "payment-api",
      "owner": "team-payments"
    }
  }
}
```

### Failing Example

No `.catalog` data present (component has no catalog-info.yaml or equivalent).

```json
{}
```

**Failure message:** `"Component is not registered in any service catalog. Add a catalog-info.yaml (Backstage) or equivalent catalog definition."`

## Remediation

When this policy fails, register the component in your service catalog:

1. **Backstage** - Create a `catalog-info.yaml` in the repository root with at minimum `apiVersion`, `kind`, `metadata.name`, and `spec.owner`
2. **Other catalogs** - Register the component in your organization's catalog system and ensure the corresponding collector is enabled
