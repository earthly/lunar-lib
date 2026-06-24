# ArgoCD Collector

Parses ArgoCD `Application`, `ApplicationSet`, and `AppProject` manifests into a normalized `.cd.argocd` view.

## Overview

This collector scans the cloned repository for ArgoCD custom resources (`apiVersion: argoproj.io/*`) and records a normalized view of the GitOps deployment configuration. It captures each Application's project, sync policy, destination, and source reference, plus the AppProjects that scope what may be deployed where. It runs on a code hook with no ArgoCD API or secrets — pure file parsing — and works equally for a dedicated GitOps repo or a component repo that ships its own ArgoCD files. The data feeds the `argocd` policy set for GitOps guardrails.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.cd.argocd.source` | object | Tool/integration metadata (`tool`, `integration`) |
| `.cd.argocd.applications[]` | array | One entry per Application/ApplicationSet (`name`, `path`, `kind`, `project`, `sync_policy`, `destination`, `source_ref`, `canary`) |
| `.cd.argocd.applications[].sync_policy` | object | Sync policy flags (`automated`, `prune`, `self_heal`) |
| `.cd.argocd.applications[].destination` | object | Deploy target (`server`, `namespace`) |
| `.cd.argocd.applications[].source_ref` | object | Manifest source (`repoURL`, `path`, `targetRevision`) |
| `.cd.argocd.applications[].template_label` | string | Golden-path template label value, when `golden_path_label` is configured |
| `.cd.argocd.applications[].component_annotation` | string | Source-component link from the `lunar.earthly.dev/component` annotation, when present |
| `.cd.argocd.projects[]` | array | AppProjects (`name`, `is_default`, `source_repos`, `destinations`) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `parse` | Parses `argoproj.io/*` custom resources from the repository into `.cd.argocd` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [gitops, kubernetes]
    # with:
    #   golden_path_label: "lunar.earthly.dev/template"
```
