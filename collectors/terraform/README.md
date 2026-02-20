# Terraform Collector

Parses Terraform HCL files and collects IaC configuration data for policy analysis.

## Overview

This collector finds all `.tf` files in a repository and parses them using [hcl2json](https://github.com/tmccombs/hcl2json). It writes file validity status and the full parsed HCL JSON, enabling downstream policies to analyze providers, modules, backend configuration, resource inventory, and infrastructure security posture.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.iac.source` | object | Tool metadata (`tool`, `version`) |
| `.iac.files[]` | array | File validity: `{path, valid, error?}` |
| `.iac.modules[]` | array | Normalized modules: `{path, resources[], analysis}` |
| `.iac.native.terraform.files[]` | array | Full parsed HCL per file: `{path, hcl}` |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `terraform` | Parses `.tf` files, writes validity and full HCL JSON |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: ["domain:your-domain"]  # Or use tags like [infra, terraform]
```
