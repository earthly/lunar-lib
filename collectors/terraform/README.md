# Terraform Collector

Parses Terraform HCL files and collects IaC configuration data for policy analysis.

## Overview

This collector finds all `.tf` files in a repository and parses them using [hcl2json](https://github.com/tmccombs/hcl2json). It writes file validity status, a normalized inventory of resources (with their tags and provider-level `default_tags`), and the full parsed HCL JSON, enabling downstream policies to analyze providers, modules, backend configuration, resource inventory, tagging, and infrastructure security posture.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.iac.source` | object | Tool metadata (`tool`, `version`) |
| `.iac.files[]` | array | File validity: `{path, valid, error?}` |
| `.iac.modules[]` | array | Normalized modules: `{path, resources[], default_tags?, analysis}` |
| `.iac.modules[].resources[]` | array | Normalized resources (see below) |
| `.iac.modules[].default_tags` | object | Provider-level default tags for the module (present only if a `provider` block sets `default_tags`) |
| `.iac.refs` | object | Backstage referential-integrity results (present only when `backstage_url` is configured) |
| `.iac.native.terraform.files[]` | array | Full parsed HCL per file: `{path, hcl}` |
| `.iac.native.terraform.cicd` | object | CI command tracking: `{cmds[], source}` |

### Normalized resource entry

Each `.iac.modules[].resources[]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Terraform resource type, e.g. `aws_s3_bucket` |
| `name` | string | Resource local name |
| `category` | string | `datastore` / `compute` / `network` / `security` / `other` |
| `has_prevent_destroy` | bool | Whether the resource sets `lifecycle { prevent_destroy = true }` |
| `internet_facing` | bool | Present (`true`) only for internet-facing load balancers / gateways |
| `tags` | object | The literal `tags = {}` map declared on the resource. Present only when the resource declares a literal tag map. Values are as-written — an interpolated value (`${var.x}`) is kept verbatim. |
| `tags_unresolved` | array | Tag keys in `tags` whose **value** is an unresolved expression (`${...}`). Present only when non-empty. A policy should skip/warn on the value of these keys (the key is present, but the value can't be verified without `terraform plan`). |
| `tags_expression` | bool | Present (`true`) only when the resource's `tags` attribute is itself a non-object expression (e.g. `tags = merge(local.common, {...})`). In this case no keys can be extracted; a policy should skip/warn rather than treat the resource as untagged. |

### Why tag values may be unresolved (hcl2json never evaluates)

`hcl2json` is a purely syntactic HCL→JSON transform; it does **not** run `terraform plan`. As a result:

- **Provider `default_tags` are invisible per-resource.** They live on the `provider "aws"` block, not on each resource. This collector captures them once per module at `.iac.modules[].default_tags` so a policy can treat every resource in the module as carrying those keys by default (and not false-positive on a repo that correctly uses `default_tags`).
- **Interpolated values arrive as literal strings.** `tags = { "k" = var.v }` comes through as `"k": "${var.v}"`, and `tags = merge(...)` comes through as the whole value being a string. The collector flags these (`tags_unresolved`, `tags_expression`) so value-level checks skip/warn instead of mis-verifying.
- **Module-provisioned resources aren't in the HCL.** Resources created inside a called module are module inputs, not `resource` blocks, so they don't appear in `.iac.modules[].resources[]` at all.

### Backstage referential integrity (`.iac.refs`)

When `backstage_url` is configured, the collector resolves each distinct concrete value of the `entity_ref_tag_key` tag against the Backstage catalog API and records the outcome under `.iac.refs`:

```json
{
  "iac": {
    "refs": {
      "checked": true,
      "entity_refs": [
        {"name": "component:default/payment-api", "exists": true},
        {"name": "component:default/legacy-svc", "exists": false},
        {"name": "component:default/flaky-lookup", "error": "HTTP 503"}
      ]
    }
  }
}
```

- `.iac.refs.checked: true` is always written when `backstage_url` is set — the "referential integrity ran" signal, so a policy can tell "configured" from "not configured".
- Each distinct concrete `entity_ref_tag_key` value records `{name, exists}` on a definitive lookup (`exists: true` on 200, `false` on 404), or `{name, error}` on a transient failure (timeout / 5xx) so an outage stays distinguishable from a real miss.
- Values that are unresolved expressions (`${...}`) are **not** looked up (there is nothing concrete to resolve).
- The namespace is derived from the ref itself — a qualified ref (`ns/name`) carries its own, a bare ref uses `default` — mirroring Backstage's own reference resolution.
- When `backstage_url` is empty (the default), no lookups run and `.iac.refs` is not written at all.

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `terraform` | Parses `.tf` files, writes validity, normalized resources + tags, and full HCL JSON |
| `cicd` | Records every `terraform` command run in CI with the CLI version |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: ["domain:your-domain"]  # Or use tags like [infra, terraform]
```

To enable Backstage referential integrity for `entity_ref` tags:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: ["domain:your-domain"]
    with:
      entity_ref_tag_key: "backstage.com/entity_ref"
      backstage_url: "https://backstage.example.com"
    secrets:
      BACKSTAGE_TOKEN: "backstage-api-token"
```
