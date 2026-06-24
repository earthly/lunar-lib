# ArgoCD Collector

Parses and validates ArgoCD `Application`, `ApplicationSet`, and `AppProject` manifests into a normalized `.cd.gitops` view.

## Overview

This collector scans the cloned repository for ArgoCD custom resources (`apiVersion: argoproj.io/*`), validates each against the argoproj CRD schemas, and records a normalized, tool-agnostic view of the GitOps deployment configuration under `.cd.gitops`. It captures each Application's project, sync policy, destination, and source reference, plus the AppProjects that scope deployments, and preserves the raw ArgoCD resource shapes under `.cd.gitops.native.argocd`. It then correlates each Application back to its source-code component and pushes the deployment posture onto that component out-of-band, so GitOps guardrails work even when ArgoCD config lives in a separate repo. The normalized data feeds the tool-agnostic `gitops` policy set.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.cd.gitops.source` | object | Tool/integration metadata (`tool`, `integration`) |
| `.cd.gitops.applications[]` | array | One entry per Application/ApplicationSet (`name`, `path`, `valid`, `kind`, `project`, `sync_policy`, `destination`, `source_ref`, `canary`) |
| `.cd.gitops.applications[].valid` | boolean | Whether the resource conforms to the argoproj CRD schema |
| `.cd.gitops.applications[].sync_policy` | object | Sync policy flags (`automated`, `prune`, `self_heal`) |
| `.cd.gitops.applications[].destination` | object | Deploy target (`server`, `namespace`) |
| `.cd.gitops.applications[].source_ref` | object | Manifest source (`repoURL`, `path`, `targetRevision`) |
| `.cd.gitops.applications[].component_annotation` | string | Source-component link from the `lunar.earthly.dev/component` annotation, when present |
| `.cd.gitops.projects[]` | array | AppProjects (`name`, `valid`, `is_default`, `source_repos`, `destinations`) |
| `.cd.gitops.linked_from` | string | On a source component: the GitOps repo the pushed posture was resolved from (written by `link-push`) |
| `.cd.gitops.native.argocd` | object | Raw, ArgoCD-specific parsed resources for advanced guardrail use |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `parse` | Parses and validates `argoproj.io/*` custom resources into `.cd.gitops` |
| `link-push` | Correlates each Application to its source component and pushes the deployment posture there out-of-band (`lunar collect --component/--sha`) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [gitops, kubernetes]
    # with:
    #   find_command: "find ./gitops -type f -name '*.yaml'"
```
