# Backstage Guardrails

Enforce Backstage service catalog standards for catalog-info.yaml completeness.

## Overview

Validates that Backstage catalog entries include required metadata for service ownership, lifecycle management, and system architecture. These checks apply to repositories that use Backstage as their service catalog and must be paired with the `backstage` collector.

The five core checks fail when no `catalog-info.yaml` is present. The four configurable checks (`required-*` / `disallowed-*`) are opt-in and skipped until configured. The two referential-integrity checks (`domain-exists`, `system-exists`) confirm the declared domain and system actually exist in Backstage; they are opt-in too — skipped (and passing) until the collector is configured with a `backstage_url`, so simply enabling them without the collector configured never turns a component red.

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
| `required-annotations` | Validates that configured annotation keys are present, and optionally that their values match typed constraints (opt-in via the `required_annotations` input) |
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
| `.catalog.native.backstage.refs.checked` | boolean | `backstage` collector — `true` when `backstage_url` is configured; both RI checks skip (pass) when absent |
| `.catalog.native.backstage.refs.domain` | object | `backstage` collector — `{ name, exists }` (or `{ name, error }` on a transient lookup failure) for `spec.domain`; read by `domain-exists` |
| `.catalog.native.backstage.refs.system` | object | `backstage` collector — `{ name, exists }` (or `{ name, error }`) for `spec.system`; read by `system-exists` |

**Note:** Ensure the `backstage` collector is configured before enabling this policy. The `domain-exists` and `system-exists` checks additionally require the collector to be configured with a `backstage_url` (and, for authenticated instances, a `BACKSTAGE_TOKEN` secret); without it they **skip (and pass)** rather than fail, since referential integrity cannot be verified. (A durable "pending" state isn't available — post-collection the SDK resolves a data-less check to fail/error, not pending — so these checks skip to pass when unverified, mirroring the opt-in `required-*` / `disallowed-*` checks.)

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

All four inputs are comma-separated lists; leave them unset (the default) and the corresponding check is skipped. `required_annotations` additionally accepts a YAML list for validating annotation *values* against typed constraints — see [Typed value constraints](#typed-value-constraints-on-required-annotations) below. Tag patterns are glob-style (`location/*` matches `location/us-east-1`), matched case-insensitively. `required-tag-patterns` needs each pattern matched by at least one tag; `disallowed-tag-patterns` fails if any tag matches any pattern. `required-annotations` needs each key present and non-empty; `disallowed-annotations` fails if any forbidden key is present at all.

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

These checks read the `.refs` block the `backstage` collector writes when it is configured with a `backstage_url`. The `.refs.checked` marker (always written when the collector is configured) is what lets the checks tell "configured" from "not configured."

> **Which check fires depends on the entity kind.** In Backstage, `spec.system` lives on `Component` entities and `spec.domain` lives on `System` entities. So `system-exists` is the everyday check (the common one-`Component`-per-repo case), while `domain-exists` only does work when the repo's `catalog-info.yaml` is itself a `kind: System` (or a `Component` carrying a custom `spec.domain`). Each check passes silently when its reference isn't declared.

**Component → system.** The declared system is a typo that doesn't resolve in Backstage:

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "kind": "Component",
        "spec": { "system": "typo-platform" },
        "refs": {
          "checked": true,
          "system": { "name": "typo-platform", "exists": false }
        }
      }
    }
  }
}
```

`system-exists` **fails**: `"System 'typo-platform' referenced in catalog-info.yaml does not exist in the Backstage catalog"`. `domain-exists` **passes** — no `spec.domain` is declared on this Component, so there's nothing to cross-reference.

**System → domain.** A `kind: System` catalog file whose declared domain does resolve:

```json
{
  "catalog": {
    "native": {
      "backstage": {
        "kind": "System",
        "spec": { "domain": "payments" },
        "refs": {
          "checked": true,
          "domain": { "name": "payments", "exists": true }
        }
      }
    }
  }
}
```

`domain-exists` **passes** (`payments` exists in Backstage).

**Not configured / transient outage — both skip (pass).** When the collector has no `backstage_url`, `.refs` is absent entirely (no `.refs.checked`) and both checks **skip (pass)** — referential integrity couldn't run, so they don't fail. If the collector *is* configured but a lookup hits a transient Backstage error, that ref is recorded as `{ "name": "...", "error": "..." }` and the corresponding check **skips (passes)** too, rather than false-failing on an outage:

```json
{ "catalog": { "native": { "backstage": {
  "refs": { "checked": true, "system": { "name": "payment-platform", "error": "502 Bad Gateway" } }
} } } }
```

### Typed value constraints on required annotations

`required-annotations` can also assert that an annotation's **value** meets a constraint, not just that the key is present. Pass `required_annotations` as a YAML list instead of a comma-separated string; each entry is either a bare key (presence-only, as before) or a mapping with a `key` and one or more constraints:

```yaml
with:
  required_annotations: |
    - key: example.com/service-tier      # integer in 0–5
      type: integer
      min: 0
      max: 5
    - key: example.com/contact-email     # must look like an email address
      type: string
      pattern: '^[^@]+@[^@]+\.[^@]+$'
    - key: example.com/environment       # one of a fixed set
      enum: [production, staging, development]
    - backstage.io/source-location       # bare key = presence-only
```

Supported constraints:

| Constraint | Applies to | Meaning |
|------------|-----------|---------|
| `type` | all | `string` (default), `integer`, `number`, or `boolean`. The value is coerced to this type before the other constraints run. |
| `min` / `max` | integer, number | Inclusive numeric bounds. |
| `min_length` / `max_length` | string | Inclusive length bounds. |
| `pattern` | string | Full-match regular expression. Quote it with single quotes (`'...'`) so backslashes pass through literally. |
| `enum` | all | The value must be one of the listed values (compared after coercion — see below). |

Backstage annotation values are strings, so `type` validates that the value *parses* as the declared type: `"2"` satisfies `type: integer`, `"2.5"` does not.

**`enum` inherits `type`.** Enum entries are coerced to the declared `type` before comparison, so the value and the allowed set are always compared in the same domain. This matters because YAML types the entries on parse: `enum: [1, 2, 3]` yields integers, but with the default `type: string` the annotation value is a string, so the entries are coerced to `"1"`, `"2"`, `"3"` and `"2"` matches. Use `type: integer` to compare as integers instead. An enum entry that can't be coerced to the declared type (e.g. `type: integer` with `enum: [1, two, 3]`) is a misconfiguration.

**Constraints must match the declared `type`.** `min`/`max` apply to `integer`/`number`; `min_length`/`max_length`/`pattern` apply to `string`; `enum` and `type` apply to any type. Pairing a constraint with the wrong type (e.g. `pattern` on an `integer`, or `min` on a `string`) is a misconfiguration, not a silent no-op.

A value that violates its constraint fails the check with a specific message (for example, `annotation "example.com/service-tier": value "7" is above maximum 5`). A malformed constraint spec — an unknown `type`, `min` greater than `max`, an invalid regex, a constraint on the wrong type, or an enum entry not of the declared type — makes the check **error** rather than fail, so the misconfiguration surfaces immediately instead of silently passing.

The comma-separated form (`required_annotations: "key1,key2"`) still works and remains presence-only; it is equivalent to a YAML list of bare keys.

## Remediation

When this policy fails, resolve it by updating your `catalog-info.yaml`:

1. **Missing file** - Create a `catalog-info.yaml` in the repository root following the [Backstage descriptor format](https://backstage.io/docs/features/software-catalog/descriptor-format)
2. **Lint errors** - Review `.catalog.native.backstage.errors[]` in the component payload and fix the reported issues
3. **Missing owner** - Add `spec.owner` with a valid team or user reference (e.g., `team-payments`)
4. **Missing lifecycle** - Add `spec.lifecycle` with a stage: `production`, `experimental`, or `deprecated`
5. **Missing system** - Add `spec.system` referencing the parent system that groups related components
6. **Referential-integrity failure** (`domain-exists` / `system-exists`) - The `spec.domain` or `spec.system` value points at an entity that does not exist in the Backstage catalog. Fix the reference to match an existing entity's `metadata.name`, or register the missing Domain/System in Backstage
