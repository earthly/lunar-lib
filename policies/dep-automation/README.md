# Dependency Automation Guardrails

Enforces that repositories have automated dependency updates configured via Dependabot or Renovate.

## Overview

Keeping dependencies up to date is a core supply-chain hygiene practice. This policy ensures that every component has at least one dependency update tool configured and that all detected package ecosystems are covered by update rules. It works with both Dependabot and Renovate, and checks pass if either tool covers the requirement.

## Policies

| Policy | Description |
|--------|-------------|
| `dep-update-tool-configured` | At least one of Dependabot or Renovate must be configured |
| `all-ecosystems-covered` | All detected package ecosystems must have update rules |

## Required Data

The `dependabot` and `renovate` collectors write **nothing** when their respective config files aren't present — object presence at `.dep_automation.dependabot` or `.dep_automation.renovate` is itself the detection signal (per [collector-reference.md § Write Nothing When Technology Not Detected](../../ai-context/collector-reference.md)). This policy uses `get_value_or_default(".", None)` to detect absent collector data.

| Path | Type | Provided By |
|------|------|-------------|
| `.dep_automation.dependabot` | object | `dependabot` collector (absent when no config file) |
| `.dep_automation.dependabot.ecosystems` | array | `dependabot` collector |
| `.dep_automation.renovate` | object | `renovate` collector (absent when no config file) |
| `.dep_automation.renovate.all_managers_enabled` | boolean | `renovate` collector |
| `.dep_automation.renovate.enabled_managers` | array | `renovate` collector |
| `.dep_automation.native.renovate` | object | `renovate` collector (raw config for reference) |
| `.lang.*` | object | Language collectors (go, nodejs, python, etc.) |
| `.containers.definitions` | array | Container collector |
| `.ci.native.github_actions` | object | GitHub Actions collector |
| `.iac` | object | IaC collector |

**Note:** Both the `dependabot` and `renovate` collectors should be configured for full coverage detection.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dep-automation@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [dep-update-tool-configured]  # Only run specific checks
```

## Examples

### Passing Example — Dependabot covers all ecosystems

`.dep_automation.renovate` is absent (no Renovate config file present).

```json
{
  "dep_automation": {
    "dependabot": {
      "valid": true,
      "ecosystems": ["docker", "github-actions", "npm"]
    }
  },
  "lang": {
    "nodejs": {}
  },
  "containers": {
    "definitions": [{"path": "Dockerfile"}]
  },
  "ci": {
    "native": {
      "github_actions": {}
    }
  }
}
```

### Passing Example — Renovate with all managers enabled

`.dep_automation.dependabot` is absent (no Dependabot config file present).

```json
{
  "dep_automation": {
    "renovate": {
      "valid": true,
      "all_managers_enabled": true,
      "enabled_managers": []
    }
  },
  "lang": {
    "go": {},
    "python": {}
  }
}
```

### Failing Example — No tool configured

Both `.dep_automation.dependabot` and `.dep_automation.renovate` are absent — neither collector wrote anything because neither config file exists.

```json
{}
```

**Failure message:** `"No dependency update tool configured. Add a .github/dependabot.yml or renovate.json to automate dependency updates."`

### Failing Example — Missing ecosystem coverage

```json
{
  "dep_automation": {
    "dependabot": {
      "valid": true,
      "ecosystems": ["npm"]
    }
  },
  "lang": {
    "nodejs": {},
    "python": {}
  }
}
```

**Failure message:** `"Missing dependency update coverage for: pip. Add update entries to Dependabot or configure Renovate."`

## Remediation

When this policy fails, you can resolve it by:

1. **No tool configured:** Add a `.github/dependabot.yml` or `renovate.json` to the repository root.
2. **Missing ecosystem coverage:** Add update entries for the missing ecosystems to your Dependabot config, or switch to Renovate which covers all detected ecosystems by default.

### Ecosystem mapping

The `all-ecosystems-covered` check is **scoped to ecosystems that map to an existing lunar-lib collector**. If a language has no collector in this repo, the policy has no signal to cross-reference against and won't flag missing coverage for it. Dependabot ecosystems like `pub` (Dart), `mix` (Elixir), `swift`, `elm`, and `gitsubmodule` are intentionally out of scope until the corresponding language collectors exist.

| Component Signal | Ecosystem Name | Provided By |
|-----------------|----------------|-------------|
| `.lang.nodejs` | `npm` | `nodejs` collector |
| `.lang.python` | `pip` | `python` collector |
| `.lang.go` | `gomod` | `golang` collector |
| `.lang.java` (maven) | `maven` | `java` collector |
| `.lang.java` (gradle) | `gradle` | `java` collector |
| `.lang.ruby` | `bundler` | `ruby` collector |
| `.lang.rust` | `cargo` | `rust` collector |
| `.lang.dotnet` | `nuget` | `dotnet` collector |
| `.lang.php` | `composer` | `php` collector |
| `.containers.definitions` | `docker` | `docker` collector |
| `.ci.native.github_actions` | `github-actions` | `github-actions` collector |
| `.iac` (terraform) | `terraform` | `terraform` collector |
