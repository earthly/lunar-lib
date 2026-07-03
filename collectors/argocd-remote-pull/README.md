# ArgoCD Remote Pull (experimental)

Runs on an **app/service repo** and materializes that service's ArgoCD deployment posture onto its **own** Component JSON, by pulling the matching `Application`(s) from a central GitOps component. Because it runs in the service's own collection, the posture lands on the sha being collected — **including a PR head sha** — so the `gitops`/`argocd` policies gate the upcoming deployment **at PR time**.

> **Status: experimental.** Read the "When to use" and "Careful" notes below before enabling.

## When to use

Enable `argocd-remote-pull` on a **service repo** when:

- The service is deployed by ArgoCD config that lives in a **separate** GitOps repo, **and**
- You want the service's deployment posture on the *service's own* component **at PR time**, so policies can gate PRs against it.

It does **no** automatic correlation — the dev team predeclares the mapping in `catalog-info.yaml` (or via inputs): which GitOps component to pull from, and which Application(s).

This is the **only** variant that can enforce at PR time. If you only want post-merge correlation/dashboards and don't want to add a mapping to each service, use [`argocd-remote-push`](../argocd-remote-push/) instead.

## Careful: don't run push and pull on the same service

Both `argocd-remote-pull` and [`argocd-remote-push`](../argocd-remote-push/) write `.cd.gitops.applications`; the hub **appends** across collection records (it never upserts), so co-enabling both on one service duplicates every `Application` entry (verdicts don't change, but coverage counts double). Pick one path per service:

| | `argocd-remote-pull` | `argocd-remote-push` |
|--|--|--|
| Runs on | the service repo | the GitOps repo |
| Service-repo config | a `catalog-info` mapping | none |
| Gates PRs | yes (lands on the PR head sha) | no (post-merge main only) |

## Predeclaring the mapping

In the service repo's `catalog-info.yaml`:

```yaml
metadata:
  annotations:
    lunar.earthly.dev/gitops-component: github.com/org/gitops
    lunar.earthly.dev/argocd-application: payment-api   # optional; omit to pull every app the GitOps component holds
```

Or pass `gitops_component` / `application` directly as inputs (bypasses `catalog-info`).

## Collected Data

Writes onto the **service's own** component (in-band, at the collected sha):

| Path | Type | Description |
|------|------|-------------|
| `.cd.gitops.applications[]` | array | The Application(s) pulled from the GitOps component |
| `.cd.gitops.projects[]` | array | The AppProjects referenced by those Applications |
| `.cd.gitops.source` | object | `{tool: argocd, integration: pull, pulled_from: <gitops-component>}` |

## Installation

Add to the **service repo's** config in `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd-remote-pull@v1.0.0
    on: ["domain:your-service-repo"]
    # with:
    #   gitops_component: "github.com/org/gitops"   # or rely on catalog-info.yaml
    #   application: "payment-api"
```

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `catalog_info_paths` | `catalog-info.yaml,catalog-info.yml` | Files to read the predeclared mapping from (first match wins) |
| `gitops_component_annotation` | `lunar.earthly.dev/gitops-component` | catalog-info annotation carrying the GitOps component id |
| `application_annotation` | `lunar.earthly.dev/argocd-application` | catalog-info annotation carrying the Application name(s); empty pulls all |
| `gitops_component` | `` | Direct override of the GitOps component id (bypasses catalog-info) |
| `application` | `` | Direct override of the Application name(s), comma-separated |
