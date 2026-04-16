# Backstage Guardrails

Enforce Backstage service catalog standards for catalog-info.yaml completeness.

## Overview

Validates that Backstage catalog entries include required metadata for service ownership, lifecycle management, and system architecture. These checks apply to repositories that use Backstage as their service catalog and should be paired with the `backstage` collector.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `catalog-info-exists` | Verifies catalog-info.yaml exists in the repository |
| `owner-set` | Validates that `spec.owner` is populated |
| `lifecycle-set` | Validates that `spec.lifecycle` is defined |
| `system-set` | Validates that `spec.system` is defined |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.catalog.exists` | boolean | `backstage` collector |
| `.catalog.entity.owner` | string | `backstage` collector |
| `.catalog.entity.lifecycle` | string | `backstage` collector |
| `.catalog.entity.system` | string | `backstage` collector |

**Note:** Ensure the `backstage` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/backstage@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [catalog-info-exists, owner-set]  # Only run specific checks
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
      "type": "service",
      "owner": "team-payments",
      "lifecycle": "production",
      "system": "payment-platform"
    }
  }
}
```

### Failing Example

```json
{
  "catalog": {
    "exists": true,
    "source": { "tool": "backstage", "file": "catalog-info.yaml" },
    "entity": {
      "name": "payment-api",
      "type": "service"
    }
  }
}
```

**Failure messages:**
- `"No catalog-info.yaml found"`
- `"Owner (spec.owner) is not set in catalog-info.yaml"`
- `"Lifecycle stage (spec.lifecycle) is not set in catalog-info.yaml"`
- `"System (spec.system) is not set in catalog-info.yaml"`

## Remediation

When this policy fails, resolve it by updating your `catalog-info.yaml`:

1. **Missing file** - Create a `catalog-info.yaml` in the repository root following the [Backstage descriptor format](https://backstage.io/docs/features/software-catalog/descriptor-format)
2. **Missing owner** - Add `spec.owner` with a valid team or user reference (e.g., `team-payments`)
3. **Missing lifecycle** - Add `spec.lifecycle` with a stage: `production`, `experimental`, or `deprecated`
4. **Missing system** - Add `spec.system` referencing the parent system that groups related components
