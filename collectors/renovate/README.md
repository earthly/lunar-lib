# Renovate Collector

Parses Renovate configuration and writes both a normalized summary and the full raw config.

## Overview

This collector scans the repository for Renovate configuration files in standard locations (`renovate.json`, `.renovaterc`, `.renovaterc.json`, or the `renovate` key in `package.json`). The full parsed config is slurped verbatim to `.dep_automation.native.renovate` for reference, and a small normalized summary (extends, enabled managers) is written to `.dep_automation.renovate` for the `dep-automation` policy to consume. Policies that need details beyond the summary (e.g. `packageRules`, `schedule`, `ignoreDeps`) can read them directly from the native config.

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
| `.dep_automation.native.renovate` | object | Full parsed Renovate config (verbatim JSON) |

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
