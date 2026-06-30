# Backstage Guardrails

Enforce Backstage service catalog standards for catalog-info.yaml completeness.

## Overview

Validates that Backstage catalog entries include required metadata for service ownership, lifecycle management, and system architecture. These checks apply to repositories that use Backstage as their service catalog and must be paired with the `backstage` collector.

**Behavior when no catalog file is present:** The core checks (`catalog-info-exists`, `catalog-info-valid`, `owner-set`, `lifecycle-set`, `system-set`) fail. A repository enabled for this policy is expected to be registered in Backstage, so a missing `catalog-info.yaml` is treated as a policy violation (not a skip). The two configurable checks (`required-annotations`, `required-tag-patterns`) are **opt-in**: they are skipped entirely until you configure them, and only then do they also fail on a missing file.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `catalog-info-exists` | Verifies catalog-info.yaml exists in the repository |
| `catalog-info-valid` | Verifies catalog-info.yaml passes lint/schema checks |
| `owner-set` | Validates that `spec.owner` is populated |
| `lifecycle-set` | Validates that `spec.lifecycle` is defined |
| `system-set` | Validates that `spec.system` is defined |
| `required-annotations` | Validates that configured annotation keys are present (opt-in via the `required_annotations` input) |
| `required-tag-patterns` | Validates that the component's tags match configured glob patterns (opt-in via the `required_tag_patterns` input) |

## Required Data

This policy reads from the following Component JSON paths. The presence of `.catalog.native.backstage` indicates that a catalog-info file was found; its absence means no file exists.

| Path | Type | Provided By |
|------|------|-------------|
| `.catalog.native.backstage` | object | `backstage` collector (namespace present ⇔ file found) |
| `.catalog.native.backstage.valid` | boolean | `backstage` collector |
| `.catalog.native.backstage.errors[]` | array | `backstage` collector |
| `.catalog.native.backstage.spec.owner` | string | `backstage` collector |
| `.catalog.native.backstage.spec.lifecycle` | string | `backstage` collector |
| `.catalog.native.backstage.spec.system` | string | `backstage` collector |
| `.catalog.native.backstage.metadata.annotations` | object | `backstage` collector (read by `required-annotations`) |
| `.catalog.native.backstage.metadata.tags` | array | `backstage` collector (read by `required-tag-patterns`) |

**Note:** Ensure the `backstage` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/backstage@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [catalog-info-exists, owner-set]  # Only run specific checks
    # Opt in to the configurable checks by setting their inputs:
    with:
      required_annotations: "backstage.io/source-location"
      required_tag_patterns: "location/*,runs-on/*"
```

`required_annotations` and `required_tag_patterns` are comma-separated lists. Leave them unset (the default) and the `required-annotations` / `required-tag-patterns` checks are skipped. Tag patterns are glob-style (`location/*` matches `location/us-east-1`), matched case-insensitively; each pattern must be matched by at least one of the component's tags.

## Examples

### Passing Example

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "valid": true,
        "errors": [],
        "path": "catalog-info.yaml",
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": { "name": "payment-api" },
        "spec": {
          "type": "service",
          "owner": "team-payments",
          "lifecycle": "production",
          "system": "payment-platform"
        }
      }
    }
  }
}
```

### Failing Example (spec fields missing)

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "valid": true,
        "errors": [],
        "path": "catalog-info.yaml",
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": { "name": "payment-api" },
        "spec": {
          "type": "service"
        }
      }
    }
  }
}
```

### Failing Example (no catalog-info.yaml)

```json
{}
```

The `.catalog.native.backstage` namespace is simply absent. The five core checks fail; the two configurable checks fail only if you have configured them (otherwise they are skipped).

**Failure messages:**
- `"No catalog-info.yaml found"`
- `"catalog-info.yaml has lint errors: <details>"`
- `"Owner (spec.owner) is not set in catalog-info.yaml"`
- `"Lifecycle stage (spec.lifecycle) is not set in catalog-info.yaml"`
- `"System (spec.system) is not set in catalog-info.yaml"`

### Configurable checks: required annotations and tag patterns

With `required_annotations: "backstage.io/source-location"` and `required_tag_patterns: "location/*,runs-on/*"` configured, this component **passes** both configurable checks:

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "metadata": {
          "annotations": { "backstage.io/source-location": "url:https://github.com/acme/payment-api" },
          "tags": ["location/us-east-1", "runs-on/self-hosted", "tier1"]
        }
      }
    }
  }
}
```

Remove the `backstage.io/source-location` annotation and `required-annotations` fails: `"catalog-info.yaml is missing required annotation(s): backstage.io/source-location"`. Drop every `runs-on/*` tag and `required-tag-patterns` fails: `"catalog-info.yaml has no tag matching required pattern(s): runs-on/*"`.

## Remediation

When this policy fails, resolve it by updating your `catalog-info.yaml`:

1. **Missing file** - Create a `catalog-info.yaml` in the repository root following the [Backstage descriptor format](https://backstage.io/docs/features/software-catalog/descriptor-format)
2. **Lint errors** - Review `.catalog.native.backstage.errors[]` in the component payload and fix the reported issues
3. **Missing owner** - Add `spec.owner` with a valid team or user reference (e.g., `team-payments`)
4. **Missing lifecycle** - Add `spec.lifecycle` with a stage: `production`, `experimental`, or `deprecated`
5. **Missing system** - Add `spec.system` referencing the parent system that groups related components
