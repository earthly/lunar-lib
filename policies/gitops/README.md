# GitOps Guardrails

Tool-agnostic GitOps continuous-delivery best practices, for any GitOps tool.

## Overview

This policy holds the GitOps checks that aren't tied to a specific tool — they read the normalized `.cd.gitops` paths, so they work for any GitOps collector (ArgoCD today, Flux later). It enforces automated sync with prune and self-heal, source-repo and destination allow-lists, and GitOps adoption coverage. Because the `argocd-remote-push` collector pushes `.cd.gitops` onto a source component from a separate GitOps repo, these guardrails apply on the service repo, not just the GitOps repo. The config checks skip cleanly when a component has no GitOps data; the `gitops-managed` coverage check inverts that, failing components that should be on GitOps but aren't. Pair it with the `argocd` policy for ArgoCD-specific checks (CRD validation, AppProject hygiene).

## Policies

This plugin provides the following guardrails (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `sync-policy` | Requires automated sync with prune and self-heal | Application sync policy is manual or missing prune/self-heal |
| `source-repo-allowlist` | Requires the manifest source repo to be allow-listed | Application source `repoURL` is not in the allow-list |
| `destination-allowlist` | Requires the destination namespace/cluster to be allow-listed | Application targets a namespace or cluster outside the allow-list |
| `gitops-managed` | Requires targeted components to actually be GitOps-managed (coverage) | A component that should be on GitOps has no resolved `.cd.gitops` data |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.cd.gitops` | object | `argocd` collector (presence = GitOps-managed; read by `gitops-managed`) |
| `.cd.gitops.applications[]` | array | `argocd` collector |
| `.cd.gitops.applications[].sync_policy` | object | `argocd` collector |
| `.cd.gitops.applications[].destination` | object | `argocd` collector |
| `.cd.gitops.applications[].source_ref` | object | `argocd` collector |
| `.catalog.entity.tags[]` | array | catalog collector (only when `gitops-managed` uses `expected_tag`) |

**Note:** Ensure the `argocd` collector is configured before enabling this policy. The `gitops-managed` check decides which components are "expected on GitOps" two ways: deploy it `on:` the tag/domain that must be GitOps-managed (e.g. `on: [production]`) and leave `expected_tag` empty, or set `expected_tag` to a catalog tag and the check only enforces on components whose `.catalog.entity.tags` carry it (populated by a catalog cataloger, e.g. from a Backstage `catalog-info.yaml`).

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: [gitops]

policies:
  # Tool-agnostic GitOps checks
  - uses: github://earthly/lunar-lib/policies/gitops@v1.0.0
    on: [gitops]
    enforcement: report-pr
    # include: [sync-policy, gitops-managed]  # Only run specific checks
    # with:
    #   allowed_source_repos: "https://github.com/org/gitops.git"
    #   allowed_destinations: "payments,checkout"
    #   expected_tag: "should-be-gitops"

  # ArgoCD-specific checks (recommended alongside)
  - uses: github://earthly/lunar-lib/policies/argocd@v1.0.0
    on: [gitops]
    enforcement: report-pr
```

## Examples

### Passing Example

An Application with automated sync, an allow-listed source, and an allowed destination:

```json
{
  "cd": {
    "gitops": {
      "applications": [
        {
          "name": "payment-api",
          "path": "apps/payment-api.yaml",
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

An Application with manual sync and no prune/self-heal:

```json
{
  "cd": {
    "gitops": {
      "applications": [
        {
          "name": "my-app",
          "path": "apps/my-app.yaml",
          "sync_policy": {"automated": false, "prune": false, "self_heal": false},
          "destination": {"server": "https://kubernetes.default.svc", "namespace": "payments"},
          "source_ref": {"repoURL": "https://github.com/org/gitops.git"}
        }
      ]
    }
  }
}
```

**Failure message:** `apps/my-app.yaml: Application 'my-app' should use an automated sync policy with prune and self-heal`

### Coverage Failure (`gitops-managed`)

A component the org expects on GitOps, with no resolved `.cd.gitops` — nothing parsed locally and nothing pushed by `argocd-remote-push` from the GitOps repo:

```json
{
  "vcs": { "provider": "github" }
}
```

**Failure message:** `Component is expected to be GitOps-managed but no GitOps Application deploys it (.cd.gitops not found). Migrate it to GitOps or exclude it from this policy's scope.`

## Remediation

When this policy fails, resolve it by:

1. **For `sync-policy` failures:** Enable automated sync with `prune: true` and `selfHeal: true` (`spec.syncPolicy.automated` in ArgoCD).
2. **For `source-repo-allowlist` failures:** Point the Application's source `repoURL` at an allow-listed repository, or add the repository to `allowed_source_repos`.
3. **For `destination-allowlist` failures:** Set the destination to an allow-listed namespace/cluster, or extend `allowed_destinations`.
4. **For `gitops-managed` failures:** Either migrate the component to GitOps (create an Application that deploys it, so `argocd-remote-push` resolves and stamps `.cd.gitops`), or narrow the policy's scope (`on:` targeting, or `expected_tag`) so it isn't expected on GitOps. This check converges once `argocd-remote-push` has processed the GitOps repo and pushed the link.

Consumers who want any of these surfaced without blocking can pin `enforcement: report-pr` at config time.
