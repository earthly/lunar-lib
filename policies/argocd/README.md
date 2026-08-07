# ArgoCD Guardrails

Enforces ArgoCD-specific GitOps hygiene: valid argoproj manifests and scoped AppProjects.

## Overview

This policy holds the checks that only make sense for ArgoCD specifically — the ones tied to ArgoCD's CRD model rather than GitOps in general. It validates Applications, ApplicationSets, and AppProjects against the argoproj CRD schemas, and requires Applications to run under a scoped (non-`default`) AppProject. It reads data parsed by the `argocd` collector and pairs with the tool-agnostic `gitops` policy set, which covers the cross-tool checks (sync policy, source/destination allow-lists, adoption coverage). Apply both together for full ArgoCD coverage.

## Policies

This plugin provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `valid` | Validates manifests against the argoproj CRD schemas | An Application/ApplicationSet/AppProject manifest is malformed or schema-invalid |
| `non-default-project` | Requires a named (non-`default`) AppProject, optionally allow-listed | Application uses the `default` AppProject or one outside the allow-list |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.cd.gitops.applications[].valid` | boolean | `argocd` collector |
| `.cd.gitops.applications[].project` | string | `argocd` collector |
| `.cd.gitops.projects[]` | array | `argocd` collector |
| `.cd.gitops.native.argocd` | object | `argocd` collector |

**Note:** Ensure the `argocd` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: [gitops]

policies:
  # ArgoCD-specific checks
  - uses: github://earthly/lunar-lib/policies/argocd@v1.0.0
    on: [gitops]
    enforcement: report-pr
    # with:
    #   allowed_projects: "platform,payments"

  # Tool-agnostic GitOps checks (recommended alongside)
  - uses: github://earthly/lunar-lib/policies/gitops@v1.0.0
    on: [gitops]
    enforcement: report-pr
```

## Examples

### Passing Example

A schema-valid Application on a scoped (non-`default`) AppProject:

```json
{
  "cd": {
    "gitops": {
      "applications": [
        {
          "name": "payment-api",
          "path": "apps/payment-api.yaml",
          "valid": true,
          "project": "platform"
        }
      ]
    }
  }
}
```

### Failing Example

A schema-invalid Application on the `default` AppProject:

```json
{
  "cd": {
    "gitops": {
      "applications": [
        {
          "name": "my-app",
          "path": "apps/my-app.yaml",
          "valid": false,
          "project": "default"
        }
      ]
    }
  }
}
```

**Failure messages:**
- `apps/my-app.yaml: Application 'my-app' is not a valid argoproj resource`
- `apps/my-app.yaml: Application 'my-app' uses the 'default' AppProject; use a scoped project`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix the malformed field flagged in the message so the resource conforms to the argoproj CRD schema (e.g. correct an `apiVersion`, a required `spec` field, or a mistyped key).
2. **For `non-default-project` failures:** Create or assign a scoped `AppProject` for the Application instead of `default` (and add it to `allowed_projects` if an allow-list is configured).

Consumers who want these surfaced without blocking can pin `enforcement: report-pr` at config time.
