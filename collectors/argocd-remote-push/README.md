# ArgoCD Remote Push Collector

Pushes each ArgoCD Application's deployment posture from a central GitOps repo onto the service component it deploys, out-of-band.

## Overview

Experimental. Runs on the repo that holds the ArgoCD files (a central GitOps repo), correlates each Application to the service component that builds its image (annotation, then image-match, then repoURL), and writes that app's deployment posture onto that service's Component JSON out-of-band, so the `gitops`/`argocd` policies evaluate on the service even though the ArgoCD config lives elsewhere. The write lands on the service's default-branch HEAD, so it only describes post-merge `main` and cannot gate PRs; use it for correlation and dashboards. Do not also run `argocd-remote-pull` on the same service: both write `.cd.gitops.applications` and the hub appends across records, so pick one path per service.

## Collected Data

This collector writes to the following Component JSON paths on each resolved service component (out-of-band):

| Path | Type | Description |
|------|------|-------------|
| `.cd.gitops.applications[]` | array | The Application(s) that deploy this service, copied from the GitOps repo |
| `.cd.gitops.source` | object | `{tool: argocd, integration: external}` |
| `.cd.gitops.linked_from` | string | The GitOps component the posture was pushed from |

## Installation

Add to the **GitOps repo's** `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd-remote-push@v1.0.0
    on: ["domain:your-gitops-repo"]
    # with:
    #   correlate_by: "annotation,image,repoURL"
```
