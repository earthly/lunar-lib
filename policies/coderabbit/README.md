# CodeRabbit Guardrails

CodeRabbit configuration and best-practices guardrails.

## Overview

This policy enforces CodeRabbit configuration standards. It validates that a CodeRabbit configuration file exists for customizing review behavior, path filters, and review instructions.

## Policies

| Policy | Severity | Description |
|--------|----------|-------------|
| `config-exists` | warning | A `.coderabbit.yaml` config file should exist at the repo root |

## Required Data

| Path | Provided By | Description |
|------|-------------|-------------|
| `.ai.native.coderabbit.config_exists` | `coderabbit` collector | Whether a CodeRabbit config file was detected |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/coderabbit@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: "${{ secrets.GH_TOKEN }}"

policies:
  - uses: github://earthly/lunar-lib/policies/coderabbit@main
    enforcement: report-pr
```

## Examples

### Passing

CodeRabbit config file exists:

```json
{
  "ai": {
    "native": {
      "coderabbit": {
        "config_file": ".coderabbit.yaml",
        "config_exists": true
      }
    }
  }
}
```

### Failing

No CodeRabbit config file found:

```json
{
  "ai": {
    "native": {
      "coderabbit": {
        "config_exists": false
      }
    }
  }
}
```

## Remediation

- **config-exists**: Create a `.coderabbit.yaml` file at the repository root. See [CodeRabbit docs](https://docs.coderabbit.ai/) for configuration options.
