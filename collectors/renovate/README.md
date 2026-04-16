# Renovate Collector

Parses Renovate configuration to collect dependency update settings and enabled managers.

## Overview

This collector scans the repository for Renovate configuration files in standard locations (`renovate.json`, `.renovaterc`, `.renovaterc.json`, or the `renovate` key in `package.json`). It parses the config to extract preset extensions, enabled managers, and package rule counts. This data feeds into the `dep-automation` policy to enforce dependency automation standards.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.dep_automation.renovate.exists` | boolean | Whether a Renovate config file was found |
| `.dep_automation.renovate.valid` | boolean | Whether the JSON config has valid syntax |
| `.dep_automation.renovate.path` | string | Path to the config file |
| `.dep_automation.renovate.extends` | array | Preset configuration names (e.g., `config:base`) |
| `.dep_automation.renovate.all_managers_enabled` | boolean | Whether all package managers are enabled (default Renovate behavior) |
| `.dep_automation.renovate.enabled_managers` | array | Explicitly enabled managers (empty if all enabled) |
| `.dep_automation.renovate.package_rules_count` | number | Number of package rules defined |

## Collectors

| Collector | Description |
|-----------|-------------|
| `config` | Parses Renovate configuration for update settings |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/renovate@v1.0.0
    on: ["domain:your-domain"]
```
