# Dependabot Collector

Parses Dependabot configuration to collect dependency update settings and covered ecosystems.

## Overview

This collector scans the repository for a `.github/dependabot.yml` configuration file and parses its contents. It extracts the schema version, update entries (package ecosystem, directory, schedule), and produces a normalized list of covered ecosystems. This data feeds into the `dep-automation` policy to enforce dependency automation standards.

## Collected Data

When no Dependabot config file is found, this collector writes nothing — object presence at `.dep_automation.dependabot` is itself the signal that Dependabot is configured. See [collector-reference.md § Write Nothing When Technology Not Detected](../../ai-context/collector-reference.md).

When a config file is found, this collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.dep_automation.dependabot.valid` | boolean | Whether the YAML config has valid syntax |
| `.dep_automation.dependabot.path` | string | Path to the config file |
| `.dep_automation.dependabot.version` | number | Dependabot schema version (typically `2`) — present when `valid: true` and the config declares it |
| `.dep_automation.dependabot.updates[]` | array | Update entries with ecosystem, directory, and schedule — present when `valid: true` |
| `.dep_automation.dependabot.ecosystems` | array | Sorted, deduplicated list of covered ecosystem names — present when `valid: true` |
| `.dep_automation.dependabot.update_count` | number | Total number of update entries — present when `valid: true` |

## Collectors

| Collector | Description |
|-----------|-------------|
| `config` | Parses `.github/dependabot.yml` for update configuration |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dependabot@v1.0.0
    on: ["domain:your-domain"]
```
