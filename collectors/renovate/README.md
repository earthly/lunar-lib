# Renovate Collector

Parses Renovate configuration and writes both a normalized summary and the full raw config.

## Overview

Scans the repository for Renovate configuration in every location Renovate itself reads. The full parsed config is slurped verbatim to `.dep_automation.native.renovate` for reference, and a small normalized summary (extends, enabled managers) is written to `.dep_automation.renovate` for the `dep-automation` policy. Config location depends on the SCM host (GitHub, GitLab, Bitbucket, Azure DevOps), not the CI environment.

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
    # with:
    #   paths: "renovate.json,.github/renovate.json"  # Override default search paths
```

### Default search paths

First match wins. When the match is `package.json`, the collector looks for a top-level `renovate` key; absence of that key is treated as "not a renovate config" before moving to the next path.

### JSON5 support

`.json5` / `.renovaterc.json5` files are parsed after stripping line (`//`) and block (`/* */`) comments and trailing commas — the common JSON5 extensions Renovate users reach for. Unquoted object keys (also allowed by JSON5) are not supported; keys must be double-quoted.

| Path | When Renovate uses it |
|------|------------------------|
| `renovate.json` | Any host |
| `renovate.json5` | Any host |
| `.github/renovate.json` | GitHub-hosted repos |
| `.github/renovate.json5` | GitHub-hosted repos |
| `.gitlab/renovate.json` | GitLab-hosted repos |
| `.gitlab/renovate.json5` | GitLab-hosted repos |
| `.renovaterc` | Any host |
| `.renovaterc.json` | Any host |
| `.renovaterc.json5` | Any host |
| `package.json` (`renovate` key) | Any host (fallback) |
