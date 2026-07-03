# ArgoCD Remote Push (experimental)

Correlates ArgoCD `Application`s in a **central GitOps repo** to the service components they deploy, and pushes each service's deployment posture onto that service's own Component JSON — **out-of-band** — so the `gitops`/`argocd` policies evaluate on the service even though the ArgoCD config lives in a different repo.

> **Status: experimental.** It performs cross-component writes (`lunar collect --component/--sha`). Read the "When to use" and "Careful" notes below before enabling.

## When to use

Enable `argocd-remote-push` on the **GitOps repo** (the one that holds the ArgoCD YAML) when:

- Your ArgoCD config lives in a central repo, separate from the services it deploys, **and**
- You want each service's deployment posture to show up on the *service's* own component **automatically, with zero configuration in the service repos**.

It correlates each Application to the component that builds its image (annotation → image-match → repoURL, first match wins) and writes the posture there.

**It cannot gate PRs.** The out-of-band write lands on the service's *default-branch HEAD*, so the posture only ever describes post-merge `main`. Use it for correlation and dashboards/scoring. If you need PR-time enforcement on the service, use [`argocd-remote-pull`](../argocd-remote-pull/) instead.

## Careful: don't run push and pull on the same service

`argocd-remote-push` and [`argocd-remote-pull`](../argocd-remote-pull/) both write `.cd.gitops.applications`. If a service is **both** push-targeted (by this collector, from the GitOps repo) **and** runs pull in its own collection, both records land at the same `(component, sha)` and the hub **appends** them (it never upserts) — so the same `Application` shows up **twice**. Policy verdicts don't flip (identical entries → same pass/fail), but coverage counts double.

**Pick one propagation path per service:**

| | `argocd-remote-push` | `argocd-remote-pull` |
|--|--|--|
| Runs on | the GitOps repo | the service repo |
| Service-repo config | none | a `catalog-info` mapping |
| Gates PRs | no (post-merge main only) | yes (lands on the PR head sha) |

(`argocd` (validate) + `argocd-remote-push` on the same GitOps repo is fine — complementary.)

## Collected Data

Writes onto each resolved **source/service** component (out-of-band):

| Path | Type | Description |
|------|------|-------------|
| `.cd.gitops.applications[]` | array | The Application(s) that deploy this service, copied from the GitOps repo |
| `.cd.gitops.source` | object | `{tool: argocd, integration: external}` |
| `.cd.gitops.linked_from` | string | The GitOps component the posture was pushed from |

## Installation

Add to the **GitOps repo's** config in `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/argocd-remote-push@v1.0.0
    on: ["domain:your-gitops-repo"]
    # with:
    #   correlate_by: "annotation,image,repoURL"
    #   component_annotation: "lunar.earthly.dev/component"
```

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `find_command` | `find . -type f \( -name '*.yaml' -o -name '*.yml' \)` | How to find candidate YAML files |
| `correlate_by` | `annotation,image,repoURL` | Ordered correlation strategies (first match wins): `annotation`, `image`, `tag`, `repoURL` |
| `component_annotation` | `lunar.earthly.dev/component` | Application annotation carrying the source component id |
| `image_registry_aliases` | `` | `old=new` registry-host aliases for image normalization |
| `tag_key` | `` | Component meta/tag field mapping a component to its app name (`tag` strategy) |
