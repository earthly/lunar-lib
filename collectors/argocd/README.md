# ArgoCD Collector

Parses and validates ArgoCD `Application`, `ApplicationSet`, and `AppProject` manifests into a normalized `.cd.gitops` view.

## Overview

This collector scans the cloned repository for ArgoCD custom resources (`apiVersion: argoproj.io/*`), validates each against the argoproj CRD schemas, and records a normalized, tool-agnostic view of the GitOps deployment configuration under `.cd.gitops`. It captures each Application's project, sync policy, destination, and source reference, plus the AppProjects that scope deployments, and preserves the raw ArgoCD resource shapes under `.cd.gitops.native.argocd`. It then surfaces that posture cross-component two ways: `link-push` writes it onto the source component out-of-band, and `link-pull` pulls it onto a service component from a `catalog-info.yaml` mapping so guardrails gate at PR time. The normalized data feeds the tool-agnostic `gitops` policy set.

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
| `.cd.gitops.source.pulled_from` | string | On a service component: the GitOps component the posture was pulled from (written by `link-pull`) |
| `.cd.gitops.native.argocd` | object | Raw, ArgoCD-specific parsed resources for advanced guardrail use |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `parse` | Parses and validates `argoproj.io/*` custom resources into `.cd.gitops` |
| `link-push` | Correlates each Application to its source component and pushes the deployment posture there out-of-band (`lunar collect --component/--sha`). Lands on the source's default-branch HEAD — a per-release system of record. |
| `link-pull` | Runs on a service repo and pulls its deployment posture from the GitOps component (`lunar component get-json`) using a mapping predeclared in `catalog-info.yaml`, materializing `.cd.gitops` onto the service itself. Lands on the sha being collected (incl. a PR head sha), so guardrails gate at PR time. |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [gitops, kubernetes]
    # with:
    #   find_command: "find ./gitops -type f -name '*.yaml'"
```
