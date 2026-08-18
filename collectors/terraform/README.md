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

### Interpreting tag values

Tags are collected **generically** — this collector records the tag keys and values a resource declares and assigns **no meaning to any particular key**. It knows nothing about service catalogs, cost-allocation schemes, or any other tagging convention.

Interpreting a tag *value* is a separate concern owned by the collector for that system. For example, resolving a Backstage entity-reference tag (`[<kind>:][<namespace>/]<name>`) against a live Backstage catalog is done by the [`backstage` collector](../backstage/README.md)'s `entity-refs` sub-collector, which reads the tags this collector wrote and records the lookup results under `.catalog.entity_refs`. That keeps Terraform parsing and catalog resolution independently useful and independently configurable.

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

To also resolve a service-catalog entity-reference tag against Backstage, add the
[`backstage` collector](../backstage/README.md) — it picks up the tags this
collector writes; no extra configuration is needed here.
