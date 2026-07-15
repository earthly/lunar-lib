# ArgoCD Deployment Gate Collector

Pulls a service's ArgoCD deployment posture from a central GitOps component onto the service's own component, gating at PR time.

## Overview

Experimental. Runs on an app/service repo: it resolves which GitOps component + Application(s) to pull, then `lunar component get-json`s them and materializes `.cd.gitops` onto the service's own component. The mapping defaults to the component's `argocd/gitops-component` (+ `argocd/application`) meta annotations set by a cataloger, falls back to explicit inputs, and optionally reads Backstage `catalog-info.yaml` when `catalog_info_paths` is set. It lands on the sha being collected — including a PR head sha — so the `gitops`/`argocd` policies gate the upcoming deployment at PR time. Don't also target the same service with `argocd-deployment-tracking` (both write `.cd.gitops.applications` and the hub appends across records, so pick one path per service).

## Collected Data

This collector writes to the following Component JSON paths on the service's own component (in-band, at the collected sha):

| Path | Type | Description |
|------|------|-------------|
| `.cd.gitops.applications[]` | array | The Application(s) pulled from the GitOps component |
| `.cd.gitops.projects[]` | array | The AppProjects referenced by those Applications |
| `.cd.gitops.source` | object | `{tool: argocd, integration: pull, pulled_from}` |

## Installation

Add to the **service repo's** `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd-deployment-gate@v1.0.0
    on: ["domain:your-service-repo"]
```

By default the mapping comes from cataloger-set component **meta annotations** — set them (typically from your own cataloger) with:

```
lunar catalog component --meta argocd/gitops-component github.com/org/gitops
lunar catalog component --meta argocd/application payment-api   # optional; omit to pull every app the GitOps component holds
```

Alternatively pass `gitops_component` / `application` directly as inputs, or **opt into** Backstage `catalog-info.yaml` by setting `catalog_info_paths` (it then reads the `lunar.earthly.dev/gitops-component` + `lunar.earthly.dev/argocd-application` annotations).
