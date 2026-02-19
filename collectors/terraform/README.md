# Terraform Collector

Parses Terraform HCL files and collects IaC configuration data for policy analysis.

## Overview

This collector finds all `.tf` files in a repository and parses them using [hcl2json](https://github.com/tmccombs/hcl2json). It writes file validity status and the full parsed HCL JSON, enabling downstream policies to analyze providers, modules, backend configuration, resource inventory, and infrastructure security posture (WAF, datastore protection, internet accessibility) — all in Python rather than bash.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.iac.source` | object | Tool metadata (`tool`, `version`) |
| `.iac.files[]` | array | File validity: `{path, valid, error?}` |
| `.iac.native.terraform.files[]` | array | Full parsed HCL per file: `{path, hcl}` |

### Design: Thin Collector, Smart Policies

The collector deliberately keeps analysis minimal — it parses HCL and writes raw JSON. All infrastructure analysis (WAF detection, datastore protection, provider version checks, etc.) happens in the `iac` and `terraform` policies in Python. This keeps the collector simple and makes checks easy to extend.

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
