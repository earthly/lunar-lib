# Terraform Collector

Parses Terraform and OpenTofu configuration files and collects IaC configuration data for policy analysis.

## Overview

This collector finds all `.tf` and `.tofu` files in a repository and parses them using [hcl2json](https://github.com/tmccombs/hcl2json). It writes file validity status and the full parsed HCL JSON, enabling downstream policies to analyze providers, modules, backend configuration, resource inventory, and infrastructure security posture.

**OpenTofu precedence.** Where a directory holds both `<base>.tf` and `<base>.tofu`, OpenTofu [uses the `.tofu` file and ignores the `.tf`](https://opentofu.org/docs/language/files/), and this collector does the same. Without that rule a policy would be evaluating configuration that is never applied.

The JSON syntax variants (`.tf.json`, `.tofu.json`) are not parsed yet.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.iac.source` | object | Tool metadata (`tool`, `version`) |
| `.iac.files[]` | array | File validity: `{path, valid, error?}` |
| `.iac.modules[]` | array | Normalized modules: `{path, resources[], analysis}` |
| `.iac.native.terraform.files[]` | array | Full parsed HCL per file: `{path, hcl}` |
| `.iac.native.terraform.cicd` | object | CI command tracking: `{cmds[], source}` |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `terraform` | Parses `.tf` files, writes validity and full HCL JSON |
| `cicd` | Records every `terraform` command run in CI with the CLI version |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: ["domain:your-domain"]  # Or use tags like [infra, terraform]
```
