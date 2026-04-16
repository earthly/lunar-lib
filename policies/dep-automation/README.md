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

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.dep_automation.dependabot` | object | `dependabot` collector |
| `.dep_automation.dependabot.exists` | boolean | `dependabot` collector |
| `.dep_automation.dependabot.ecosystems` | array | `dependabot` collector |
| `.dep_automation.renovate` | object | `renovate` collector |
| `.dep_automation.renovate.exists` | boolean | `renovate` collector |
| `.dep_automation.renovate.all_managers_enabled` | boolean | `renovate` collector |
| `.dep_automation.renovate.enabled_managers` | array | `renovate` collector |
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

```json
{
  "dep_automation": {
    "dependabot": {
      "exists": true,
      "ecosystems": ["docker", "github-actions", "npm"]
    },
    "renovate": {
      "exists": false
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

```json
{
  "dep_automation": {
    "dependabot": {
      "exists": false
    },
    "renovate": {
      "exists": true,
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

```json
{
  "dep_automation": {
    "dependabot": {
      "exists": false
    },
    "renovate": {
      "exists": false
    }
  }
}
```

**Failure message:** `"No dependency update tool configured. Add a .github/dependabot.yml or renovate.json to automate dependency updates."`

### Failing Example — Missing ecosystem coverage

```json
{
  "dep_automation": {
    "dependabot": {
      "exists": true,
      "ecosystems": ["npm"]
    },
    "renovate": {
      "exists": false
    }
  },
  "lang": {
    "nodejs": {},
    "python": {}
  }
}
```

**Failure message:** `"Missing dependency update coverage for: pip (python). Add update entries to Dependabot or configure Renovate."`

## Remediation

When this policy fails, you can resolve it by:

1. **No tool configured:** Add a `.github/dependabot.yml` or `renovate.json` to the repository root.
2. **Missing ecosystem coverage:** Add update entries for the missing ecosystems to your Dependabot config, or switch to Renovate which covers all detected ecosystems by default.

### Ecosystem mapping

The policy maps detected component data to Dependabot ecosystem names:

| Component Signal | Ecosystem Name |
|-----------------|----------------|
| `.lang.nodejs` | `npm` |
| `.lang.python` | `pip` |
| `.lang.go` | `gomod` |
| `.lang.java` (maven) | `maven` |
| `.lang.java` (gradle) | `gradle` |
| `.lang.ruby` | `bundler` |
| `.lang.rust` | `cargo` |
| `.lang.dotnet` | `nuget` |
| `.containers.definitions` | `docker` |
| `.ci.native.github_actions` | `github-actions` |
| `.iac` (terraform) | `terraform` |
