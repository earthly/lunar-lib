# ArgoCD Guardrails

Enforces ArgoCD GitOps best practices for safe, standardized continuous delivery.

## Overview

This policy validates ArgoCD configuration parsed by the `argocd` collector against GitOps best practices: automated sync with prune and self-heal, scoped (non-default) AppProjects, source-repo and destination allow-lists, golden-path templates, and progressive delivery for critical services. Every check skips cleanly when a component has no ArgoCD configuration, so it is safe to apply broadly and enforce only where GitOps is in use. Use `include`/`exclude` to pick the checks that match your platform conventions.

## Policies

This plugin provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `golden-path-template` | Requires each Application to carry the golden-path template label | Application is missing the standard template label |
| `sync-policy` | Requires automated sync with prune and self-heal | Application sync policy is manual or missing prune/self-heal |
| `non-default-project` | Requires a named (non-`default`) AppProject, optionally allow-listed | Application uses the `default` project or one outside the allow-list |
| `source-repo-allowlist` | Requires the manifest source repo to be allow-listed | Application source `repoURL` is not in the allow-list |
| `destination-allowlist` | Requires the destination namespace/cluster to be allow-listed | Application targets a namespace or cluster outside the allow-list |
| `canary-for-critical` | Requires Argo Rollouts for critical-tier components | A critical-tagged component deploys without a canary/blue-green rollout |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.cd.argocd.applications[]` | array | `argocd` collector |
| `.cd.argocd.applications[].sync_policy` | object | `argocd` collector |
| `.cd.argocd.applications[].destination` | object | `argocd` collector |
| `.cd.argocd.applications[].source_ref` | object | `argocd` collector |
| `.cd.argocd.applications[].template_label` | string | `argocd` collector |
| `.cd.argocd.applications[].canary` | object | `argocd` collector |

**Note:** Ensure the `argocd` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: [gitops]

policies:
  - uses: github://earthly/lunar-lib/policies/argocd@v1.0.0
    on: [gitops]
    enforcement: report-pr
    # include: [sync-policy, non-default-project]  # Only run specific checks
    # with:
    #   allowed_projects: "platform,payments"
    #   allowed_source_repos: "https://github.com/org/gitops.git"
    #   allowed_destinations: "payments,checkout"
    #   critical_tags: "critical,tier1"
```

## Examples

### Passing Example

An Application with automated sync, a named project, an allow-listed source, and a golden-path label:

```json
{
  "cd": {
    "argocd": {
      "applications": [
        {
          "name": "payment-api",
          "path": "apps/payment-api.yaml",
          "project": "platform",
          "template_label": "standard-v2",
          "sync_policy": {"automated": true, "prune": true, "self_heal": true},
          "destination": {"server": "https://kubernetes.default.svc", "namespace": "payments"},
          "source_ref": {"repoURL": "https://github.com/org/gitops.git"},
          "canary": {"rollout": true}
        }
      ]
    }
  }
}
```

### Failing Example

An Application on the `default` project with manual sync and no prune/self-heal:

```json
{
  "cd": {
    "argocd": {
      "applications": [
        {
          "name": "my-app",
          "path": "apps/my-app.yaml",
          "project": "default",
          "sync_policy": {"automated": false, "prune": false, "self_heal": false},
          "destination": {"server": "https://kubernetes.default.svc", "namespace": "default"},
          "source_ref": {"repoURL": "https://github.com/other/repo.git"}
        }
      ]
    }
  }
}
```

**Failure messages:**
- `apps/my-app.yaml: Application 'my-app' should use an automated sync policy with prune and self-heal`
- `apps/my-app.yaml: Application 'my-app' uses the 'default' AppProject; use a scoped project`

## Remediation

When this policy fails, resolve it by:

1. **For `golden-path-template` failures:** Add the configured golden-path label/annotation to the Application (best injected once by your golden-path manifest generator).
2. **For `sync-policy` failures:** Set `spec.syncPolicy.automated` with `prune: true` and `selfHeal: true`.
3. **For `non-default-project` failures:** Move the Application to a scoped `AppProject` (and add it to `allowed_projects` if an allow-list is configured).
4. **For `source-repo-allowlist` failures:** Point `spec.source.repoURL` at an allow-listed repository, or add the repository to `allowed_source_repos`.
5. **For `destination-allowlist` failures:** Set `spec.destination` to an allow-listed namespace/cluster, or extend `allowed_destinations`.
6. **For `canary-for-critical` failures:** Deploy critical-tier components via an Argo Rollouts `Rollout` with a canary or blue-green strategy instead of a plain Deployment.

Consumers who want any of these surfaced without blocking can pin `enforcement: report-pr` at config time.
