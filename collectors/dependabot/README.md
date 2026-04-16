# Dependabot Collector

Parses Dependabot configuration to collect dependency update settings and covered ecosystems.

## Overview

This collector scans the repository for a `.github/dependabot.yml` configuration file and parses its contents. It extracts the schema version, update entries (package ecosystem, directory, schedule), and produces a normalized list of covered ecosystems. This data feeds into the `dep-automation` policy to enforce dependency automation standards.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.dep_automation.dependabot.exists` | boolean | Whether a Dependabot config file was found |
| `.dep_automation.dependabot.valid` | boolean | Whether the YAML config has valid syntax |
| `.dep_automation.dependabot.path` | string | Path to the config file |
| `.dep_automation.dependabot.version` | number | Dependabot schema version (typically `2`) |
| `.dep_automation.dependabot.updates[]` | array | Update entries with ecosystem, directory, and schedule |
| `.dep_automation.dependabot.ecosystems` | array | Sorted, deduplicated list of covered ecosystem names |
| `.dep_automation.dependabot.update_count` | number | Total number of update entries |

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
