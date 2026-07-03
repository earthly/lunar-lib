# ArgoCD Collector

Parses and validates ArgoCD `Application`, `ApplicationSet`, and `AppProject` manifests into a normalized `.cd.gitops` view.

## Overview

This collector scans the cloned repository for ArgoCD custom resources (`apiVersion: argoproj.io/*`), validates each against the argoproj CRD schemas with kubeconform, and records a normalized, tool-agnostic view of the GitOps config under `.cd.gitops` on the repo's own component. It captures each Application's project, sync policy, destination, and source reference, plus the AppProjects that scope deployments, and preserves the raw resource shapes under `.cd.gitops.native.argocd`. The normalized data feeds the tool-agnostic `gitops` and ArgoCD-specific `argocd` policy sets. When the ArgoCD config lives in a separate repo, the companion `argocd-remote-push` and `argocd-remote-pull` collectors carry the posture cross-component (use one per service, not both).

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.cd.gitops.source` | object | Tool/integration metadata (`tool`, `integration`) |
| `.cd.gitops.applications[]` | array | One entry per Application/ApplicationSet (`name`, `path`, `valid`, `kind`, `project`, `sync_policy`, `destination`, `source_ref`, `canary`) |
| `.cd.gitops.applications[].valid` | boolean | Whether the resource conforms to the argoproj CRD schema |
| `.cd.gitops.applications[].sync_policy` | object | Sync policy flags (`automated`, `prune`, `self_heal`) |
| `.cd.gitops.applications[].destination` | object | Deploy target (`server`, `name`, `namespace`) |
| `.cd.gitops.applications[].source_ref` | object | Manifest source (`repoURL`, `path`, `targetRevision`) |
| `.cd.gitops.projects[]` | array | AppProjects (`name`, `valid`, `is_default`, `source_repos`, `destinations`) |
| `.cd.gitops.native.argocd` | object | Raw, ArgoCD-specific parsed resources for advanced guardrail use |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [gitops, kubernetes]
    # with:
    #   find_command: "find ./gitops -type f -name '*.yaml'"
```
