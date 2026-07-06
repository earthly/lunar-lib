# Backstage Guardrails

Enforce Backstage service catalog standards for catalog-info.yaml completeness.

## Overview

Validates that Backstage catalog entries include required metadata for service ownership, lifecycle management, and system architecture. These checks apply to repositories that use Backstage as their service catalog and must be paired with the `backstage` collector.

The five core checks fail when no `catalog-info.yaml` is present. The four configurable checks (`required-*` / `disallowed-*`) are opt-in and skipped until configured. The two referential-integrity checks (`domain-exists`, `system-exists`) confirm the declared domain and system actually exist in Backstage, and stay pending until the collector is configured with a `backstage_url`.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `catalog-info-exists` | Verifies catalog-info.yaml exists in the repository |
| `catalog-info-valid` | Verifies catalog-info.yaml passes lint/schema checks |
| `owner-set` | Validates that `spec.owner` is populated |
| `lifecycle-set` | Validates that `spec.lifecycle` is defined |
| `system-set` | Validates that `spec.system` is defined |
| `domain-exists` | Verifies the declared `spec.domain` exists in Backstage (needs collector `backstage_url`) |
| `system-exists` | Verifies the declared `spec.system` exists in Backstage (needs collector `backstage_url`) |
| `required-annotations` | Validates that configured annotation keys are present (opt-in via the `required_annotations` input) |
| `required-tag-patterns` | Validates that the component's tags match configured glob patterns (opt-in via the `required_tag_patterns` input) |
| `disallowed-annotations` | Fails if any forbidden annotation key is present (opt-in via the `disallowed_annotations` input) |
| `disallowed-tag-patterns` | Fails if any tag matches a forbidden glob pattern (opt-in via the `disallowed_tag_patterns` input) |

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
| `.catalog.native.backstage.metadata.annotations` | object | `backstage` collector (read by `required-annotations` / `disallowed-annotations`) |
| `.catalog.native.backstage.metadata.tags` | array | `backstage` collector (read by `required-tag-patterns` / `disallowed-tag-patterns`) |
| `.catalog.native.backstage.refs.domain` | object | `backstage` collector — `{ name, exists }` for `spec.domain`; read by `domain-exists` |
| `.catalog.native.backstage.refs.system` | object | `backstage` collector — `{ name, exists }` for `spec.system`; read by `system-exists` |

**Note:** Ensure the `backstage` collector is configured before enabling this policy. The `domain-exists` and `system-exists` checks additionally require the collector to be configured with a `backstage_url` (and, for authenticated instances, a `BACKSTAGE_TOKEN` secret); without it they stay **pending** because referential integrity cannot be verified.

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
      disallowed_annotations: "backstage.io/skip-checks"
      disallowed_tag_patterns: "deprecated/*"
```

All four inputs are comma-separated lists; leave them unset (the default) and the corresponding check is skipped. Tag patterns are glob-style (`location/*` matches `location/us-east-1`), matched case-insensitively. `required-tag-patterns` needs each pattern matched by at least one tag; `disallowed-tag-patterns` fails if any tag matches any pattern. `required-annotations` needs each key present and non-empty; `disallowed-annotations` fails if any forbidden key is present at all.

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

The `.catalog.native.backstage` namespace is simply absent. The five core checks fail. The `required-*` checks fail too if configured; the `disallowed-*` checks **pass** (nothing forbidden can be present without a file). All four are skipped if unconfigured.

**Failure messages:**
- `"No catalog-info.yaml found"`
- `"catalog-info.yaml has lint errors: <details>"`
- `"Owner (spec.owner) is not set in catalog-info.yaml"`
- `"Lifecycle stage (spec.lifecycle) is not set in catalog-info.yaml"`
- `"System (spec.system) is not set in catalog-info.yaml"`

### Configurable checks: required and disallowed annotations / tag patterns

With `required_annotations: "backstage.io/source-location"`, `required_tag_patterns: "location/*,runs-on/*"`, `disallowed_annotations: "backstage.io/skip-checks"`, and `disallowed_tag_patterns: "deprecated/*"` configured, this component **passes** all four configurable checks:

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

Remove the `backstage.io/source-location` annotation and `required-annotations` fails: `"catalog-info.yaml is missing required annotation(s): backstage.io/source-location"`. Drop every `runs-on/*` tag and `required-tag-patterns` fails: `"catalog-info.yaml has no tag matching required pattern(s): runs-on/*"`. Conversely, add a `backstage.io/skip-checks` annotation and `disallowed-annotations` fails; add a `deprecated/legacy` tag and `disallowed-tag-patterns` fails: `"catalog-info.yaml has tag(s) matching disallowed pattern(s): deprecated/* (deprecated/legacy)"`.

### Referential integrity: domain-exists and system-exists

These checks read the `.refs` block the `backstage` collector writes when it is configured with a `backstage_url`. Here the declared domain resolves in Backstage but the system is a typo that does not:

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "spec": { "domain": "payments", "system": "typo-platform" },
        "refs": {
          "domain": { "name": "payments", "exists": true },
          "system": { "name": "typo-platform", "exists": false }
        }
      }
    }
  }
}
```

`domain-exists` **passes** (`payments` exists in Backstage). `system-exists` **fails**: `"System 'typo-platform' referenced in catalog-info.yaml does not exist in the Backstage catalog"`. When a component declares no `spec.domain` / `spec.system`, the corresponding check **passes** (nothing to cross-reference). When the collector has no `backstage_url` configured, `.refs` is absent and both checks are **pending** — referential integrity could not be verified — rather than failing.

## Remediation

When this policy fails, resolve it by updating your `catalog-info.yaml`:

1. **Missing file** - Create a `catalog-info.yaml` in the repository root following the [Backstage descriptor format](https://backstage.io/docs/features/software-catalog/descriptor-format)
2. **Lint errors** - Review `.catalog.native.backstage.errors[]` in the component payload and fix the reported issues
3. **Missing owner** - Add `spec.owner` with a valid team or user reference (e.g., `team-payments`)
4. **Missing lifecycle** - Add `spec.lifecycle` with a stage: `production`, `experimental`, or `deprecated`
5. **Missing system** - Add `spec.system` referencing the parent system that groups related components
6. **Referential-integrity failure** (`domain-exists` / `system-exists`) - The `spec.domain` or `spec.system` value points at an entity that does not exist in the Backstage catalog. Fix the reference to match an existing entity's `metadata.name`, or register the missing Domain/System in Backstage
