# ArgoCD Deployment Gate Collector

Pulls a service's ArgoCD deployment posture from a central GitOps component onto the service's own component, gating at PR time.

## Overview

Experimental. Runs on an app/service repo, reads a predeclared app-to-Application mapping from `catalog-info.yaml` (or direct inputs), pulls the matching Application(s) from the central GitOps component via `lunar component get-json`, and materializes `.cd.gitops` onto the service's own component. Because it runs in the service's own collection it lands on the sha being collected — including a PR head sha — so the `gitops`/`argocd` policies gate the upcoming deployment at PR time, the only variant that enforces on PRs. Do not also target the same service with `argocd-deployment-tracking`: both write `.cd.gitops.applications` and the hub appends across records, so pick one path per service.

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

Predeclare the mapping in the service repo's `catalog-info.yaml`:

```yaml
metadata:
  annotations:
    lunar.earthly.dev/gitops-component: github.com/org/gitops
    lunar.earthly.dev/argocd-application: payment-api
```

Or pass `gitops_component` / `application` directly as inputs.
