# GitOps Guardrails

Enforces GitOps continuous-delivery best practices for safe, standardized deployments.

## Overview

This policy validates GitOps configuration against continuous-delivery best practices: schema-valid manifests, automated sync with prune and self-heal, scoped (non-`default`) projects, and source-repo and destination allow-lists. It reads the tool-agnostic `.cd.gitops` paths — including data link-pushed onto a source component from a separate GitOps repo by the `argocd` collector — so the same guardrails apply on the service repo, not just the GitOps repo. The config checks skip cleanly when a component has no GitOps data; the `gitops-managed` coverage check inverts that, failing components that should be on GitOps but aren't (migration visibility). Use `include`/`exclude` to pick the checks that match your conventions.

## Policies

This plugin provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `valid` | Validates manifests against the argoproj CRD schemas | An Application/AppProject manifest is malformed or schema-invalid |
| `sync-policy` | Requires automated sync with prune and self-heal | Application sync policy is manual or missing prune/self-heal |
| `non-default-project` | Requires a named (non-`default`) project, optionally allow-listed | Application uses the `default` project or one outside the allow-list |
| `source-repo-allowlist` | Requires the manifest source repo to be allow-listed | Application source `repoURL` is not in the allow-list |
| `destination-allowlist` | Requires the destination namespace/cluster to be allow-listed | Application targets a namespace or cluster outside the allow-list |
| `gitops-managed` | Requires targeted components to actually be on ArgoCD (coverage) | A component that should be GitOps-managed has no resolved `.cd.gitops` data |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.cd.gitops` | object | `argocd` collector (presence = GitOps-managed; read by `gitops-managed`) |
| `.cd.gitops.applications[]` | array | `argocd` collector |
| `.cd.gitops.applications[].valid` | boolean | `argocd` collector |
| `.cd.gitops.applications[].sync_policy` | object | `argocd` collector |
| `.cd.gitops.applications[].destination` | object | `argocd` collector |
| `.cd.gitops.applications[].source_ref` | object | `argocd` collector |
| `.cd.gitops.projects[]` | array | `argocd` collector |

**Note:** Ensure the `argocd` collector is configured before enabling this policy. The `gitops-managed` check also reads the component's Lunar tags (to decide which components are expected on GitOps); the expected-on-GitOps signal can be set manually or by a cataloger.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: [gitops]

policies:
  - uses: github://earthly/lunar-lib/policies/gitops@v1.0.0
    on: [gitops]
    enforcement: report-pr
    # include: [valid, sync-policy, non-default-project]  # Only run specific checks
    # with:
    #   allowed_projects: "platform,payments"
    #   allowed_source_repos: "https://github.com/org/gitops.git"
    #   allowed_destinations: "payments,checkout"
```

## Examples

### Passing Example

A schema-valid Application with automated sync, a named project, and an allow-listed source:

```json
{
  "cd": {
    "gitops": {
      "applications": [
        {
          "name": "payment-api",
          "path": "apps/payment-api.yaml",
          "valid": true,
          "project": "platform",
          "sync_policy": {"automated": true, "prune": true, "self_heal": true},
          "destination": {"server": "https://kubernetes.default.svc", "namespace": "payments"},
          "source_ref": {"repoURL": "https://github.com/org/gitops.git"}
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
    "gitops": {
      "applications": [
        {
          "name": "my-app",
          "path": "apps/my-app.yaml",
          "valid": true,
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
- `apps/my-app.yaml: Application 'my-app' uses the 'default' project; use a scoped AppProject`

### Coverage Failure (`gitops-managed`)

A component the org expects on GitOps, with no resolved ArgoCD Application (no `.cd.gitops` — nothing parsed locally and nothing link-pushed from the GitOps repo):

```json
{
  "vcs": { "provider": "github" }
}
```

**Failure message:** `Component is expected to be GitOps-managed but no ArgoCD Application deploys it (.cd.gitops not found). Migrate it to ArgoCD or exclude it from this policy's scope.`

## Remediation

When this policy fails, resolve it by:

1. **For `valid` failures:** Fix the malformed field flagged in the message so the resource conforms to the argoproj CRD schema.
2. **For `sync-policy` failures:** Set `spec.syncPolicy.automated` with `prune: true` and `selfHeal: true`.
3. **For `non-default-project` failures:** Move the Application to a scoped `AppProject` (and add it to `allowed_projects` if an allow-list is configured).
4. **For `source-repo-allowlist` failures:** Point `spec.source.repoURL` at an allow-listed repository, or add the repository to `allowed_source_repos`.
5. **For `destination-allowlist` failures:** Set `spec.destination` to an allow-listed namespace/cluster, or extend `allowed_destinations`.
6. **For `gitops-managed` failures:** Either migrate the component to ArgoCD (create an `Application` that deploys it, so `link-push` resolves and stamps `.cd.gitops`), or narrow the policy's scope (`on:` targeting, or `expected_tag`) so it isn't expected on GitOps. This check converges once the `argocd` collector has processed the GitOps repo and pushed the link.

Consumers who want any of these surfaced without blocking can pin `enforcement: report-pr` at config time.
