# Terraform Collector

Parses Terraform and OpenTofu configuration files and collects IaC configuration data for policy analysis.

## Overview

This collector finds every configuration file the language accepts — `.tf`, `.tofu`, `.tf.json` and `.tofu.json` — and writes file validity status plus the full parsed JSON, enabling downstream policies to analyze providers, modules, backend configuration, resource inventory, and infrastructure security posture.

HCL files go through [hcl2json](https://github.com/tmccombs/hcl2json); the `.json` variants are already in the target format and are read directly.

**OpenTofu precedence.** Where a directory holds both `<base>.tf` and `<base>.tofu`, OpenTofu [uses the `.tofu` file and ignores the `.tf`](https://opentofu.org/docs/language/files/), and this collector does the same. Without that rule a policy would be evaluating configuration that is never applied.

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
