# Terraform Collector

Parses Terraform and OpenTofu configuration files and collects IaC configuration data for policy analysis.

## Overview

This collector finds all `.tf` and `.tofu` files in a repository and parses them using [hcl2json](https://github.com/tmccombs/hcl2json). It writes file validity status, normalized resources (with their tags and provider-level `default_tags`), and the full parsed HCL JSON, enabling downstream policies to analyze providers, modules, backend configuration, resource inventory, tagging, and infrastructure security posture.

**OpenTofu precedence.** Where a directory holds both `<base>.tf` and `<base>.tofu`, OpenTofu [uses the `.tofu` file and ignores the `.tf`](https://opentofu.org/docs/language/files/), and this collector does the same. Without that rule a policy would be evaluating configuration that is never applied.

The JSON syntax variants (`.tf.json`, `.tofu.json`) are not parsed yet.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.iac.source` | object | Tool metadata (`tool`, `version`) |
| `.iac.files[]` | array | File validity: `{path, valid, error?}` |
| `.iac.modules[]` | array | Normalized modules: `{path, resources[], default_tags?, analysis}` |
| `.iac.modules[].resources[]` | array | Normalized resources (see below) |
| `.iac.modules[].default_tags` | object | Provider `default_tags` that apply to the module's resources: from its own `provider "aws"` blocks, or, if it has none, from the modules that call it by local path. Present only when non-empty. |
| `.iac.modules[].default_tags_inherited_from` | array | Paths of the calling modules the `default_tags` came from. Present only when inherited. |
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
| `tags` | object | The literal `tags = {}` map, as written: an interpolated value stays `${var.x}`. Present only when the resource declares a literal map. |
| `tags_unresolved` | array | Keys in `tags` whose value is an unresolved expression (`${...}`). Present only when non-empty. |
| `tags_expression` | bool | `true` when `tags` is itself an expression (e.g. `merge(local.common, {...})`), so no keys can be read. Present only when true. |

### Tags are not evaluated

`hcl2json` parses HCL without running `terraform plan`, so:

- Provider `default_tags` sit on the `provider "aws"` block, not on each resource; they're recorded once per module at `.iac.modules[].default_tags`. A module directory with no `provider "aws"` block inherits them, as Terraform does, from the modules that call it with a local `source` (`./modules/queue`), following the call chain; with several callers it takes their union. A provider-less module nothing in the repo calls gets none.
- Interpolated values arrive as literal strings (`"${var.v}"`) and `tags = merge(...)` as a single string; both are flagged (`tags_unresolved`, `tags_expression`).
- Resources inside a remote module (a registry or Git `source`) aren't in this repo, so they're absent from `resources[]`. Local modules are ordinary directories and do appear.

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
    include:
      - terraform  # Parses .tf files
      - cicd       # terraform commands in CI
```

To also resolve a service-catalog entity-reference tag against Backstage, add the
[`backstage` collector](../backstage/README.md) — it picks up the tags this
collector writes; no extra configuration is needed here.
