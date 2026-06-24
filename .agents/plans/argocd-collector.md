# ArgoCD Validation Collector + Policies — Plan

A reusable ArgoCD guardrail set: parse ArgoCD config, validate it, and (the hard
part) correlate ArgoCD config back to the source component when the two live in
**separate repos**. This ticket describes the **options we will implement in the
first pass** and is explicit about what's deferred and why.

---

## Motivation

ArgoCD is the dominant GitOps CD tool. Two realities shape this work:

1. **ArgoCD config often lives in a different repo from the application source.**
   Large orgs keep a central/per-team GitOps repo (frequently the output of a
   "golden-path" manifest generator using the rendered-manifest pattern), separate
   from each service's source repo. So an `Application` and the code it deploys are
   usually in different components.
2. **Nothing in ArgoCD records the link back to the source component.** An
   `Application` only declares *where the manifests are* (`spec.source.repoURL`) and
   *where they deploy* (`spec.destination`). The mapping to the owning
   source-code component is implicit (folder structure, CODEOWNERS, naming, a
   catalog, or a proprietary platform tool) — never a standard machine-readable
   field. See the discussion in "Correlation" below.

So the collector is easy; **correlating ArgoCD config to the right component is the
real design problem**, and we solve it with a small set of configurable strategies
plus a fork escape hatch.

---

## First-pass scope

| Phase | What | Confidence |
|-------|------|-----------|
| **1 (build now)** | `argocd` collector (local parse) + `argocd` policy set + correlation via **annotation** (default) and **repoURL-normalize** fallback | High — no platform dependencies |
| **2 (opt-in, same tier)** | `argocd-link` cataloger adding **image-match** and **catalog/tag** correlation strategies | Medium — depends on other collectors/catalog |
| **Deferred (verify first)** | rich cross-component data **push**, `ApplicationSet` generator resolution, **API/fork** source adapter | Blocked / needs verification |

---

## Component 1 — `argocd` collector (local parse)

A `code`-hook collector that scans the cloned repo for ArgoCD CRDs
(`apiVersion: argoproj.io/*`) and writes a normalized view to its **own**
Component JSON. Works in both modes with no special handling:

- a dedicated GitOps/ArgoCD repo (finds many `Application`s), and
- a component repo that ships its own ArgoCD files (finds its own).

Generalizes the existing demo collectors (raw inventory + the single-template
check) into one normalized schema. Composes with the existing `k8s` and `docker`
collectors (it does not re-parse workloads — it references them).

### Proposed schema: `.cd.argocd`

```jsonc
{
  "cd": {
    "argocd": {
      "applications": [
        {
          "name": "payment-api",
          "path": "apps/payment-api.yaml",
          "kind": "Application",              // or ApplicationSet
          "project": "platform",
          "template_label": "standard-v2",    // configurable golden-path label, if present
          "sync_policy": { "automated": true, "prune": true, "self_heal": true },
          "destination": { "server": "...", "namespace": "payments" },
          "source_ref": { "repoURL": "https://github.com/org/gitops.git",
                          "path": "payment-api", "targetRevision": "HEAD" },
          "images": ["myregistry.io/payment-api"],   // if statically resolvable (see Correlation)
          "canary": { "rollout": true }              // Argo Rollouts referenced
        }
      ],
      "projects": [
        { "name": "platform", "is_default": false,
          "source_repos": ["https://github.com/org/gitops.git"],
          "destinations": [{ "namespace": "payments", "server": "..." }] }
      ]
    }
  }
}
```

Notes:
- Tool-agnostic key (`.cd.argocd`) so policies don't care whether data came from
  files (now) or an API (later).
- `images` is best-effort: only populated when the referenced workload manifests
  are plain YAML in the same repo/path. Helm/templated/generated manifests will
  often leave it empty — that's expected (see Correlation caveats).

---

## Component 2 — `argocd` policy set

Checks that run on whichever component holds the ArgoCD files (one check per file,
`include`/`exclude`-able). All resolve to skip when `.cd.argocd` is absent (vendor
not in use), per the skip-vs-fail convention.

- `golden-path-template` — `Application` carries the configured golden-path label/template (configurable; skip if no template configured).
- `sync-policy` — `syncPolicy.automated` with `prune` + `selfHeal` true.
- `non-default-project` — `spec.project` is not `default` and is within an allow-list.
- `source-repo-allowlist` — `source.repoURL` within configured allowed repos.
- `destination-allowlist` — destination namespace/cluster within allow-list.
- `canary-for-critical` — Argo Rollouts present for components tagged critical-tier (criticality-tiered enforcement).

---

## Component 3 — Cross-component correlation (`argocd-link` cataloger)

When the ArgoCD files and the source component are different repos, we need to
attach the deployment posture (or at least a link) to the **source component**.

Mechanism: a **cataloger** (catalogers can write tags/`meta` to *other*
components, and aren't sha-keyed). It reads the GitOps repo's `.cd.argocd`,
resolves each `Application` to a component, and stamps the target component with a
tag (`argocd-managed`) and `meta` (e.g. `argo_app`, `argo_project`, sync-policy
booleans). Policies on the source component then read those.

### Correlation strategies (configurable, first-match-wins)

The link key can live in four places; the resolver tries them in order and logs
which one resolved each link.

| # | Strategy | Where the key lives | Default | Requires | Honest coverage |
|---|----------|---------------------|---------|----------|-----------------|
| 1 | **Annotation** | producer: an annotation on the `Application` (e.g. `lunar.earthly.dev/component: github.com/org/app`) | ✅ on | a convention (best injected once by a golden-path generator) | Deterministic. Not a pre-existing industry standard, but cheap to adopt and the most reliable. |
| 2 | **Image match** | natural key: `Application` deployed image ↔ component's built image (`.containers.builds[].image` from the `docker` collector) | opt-in input | `docker` collector enabled + image statically resolvable | Best *automatic* path. Misses jib/Bazel/ko/Kaniko builds (no `docker build` captured) and templated images; needs registry normalization. |
| 3 | **Catalog / tag** | consumer: component carries a tag/`meta` mapping (often from an existing catalog) | opt-in input | a source of truth (e.g. Backstage `source-location`, already ingested by the `backstage` collector) | Strong for catalog-mature orgs. Not a bootstrap method — needs the mapping to already exist somewhere. |
| 4 | **repoURL normalize** | natural key: normalize `source.repoURL` → component id | ✅ fallback | nothing | Only correct when manifests are co-located with source or the GitOps repo *is* the target. Weak in the separate-repo case (repoURL = manifests repo, not app). |
| — | **Fork** | custom | n/a | code change | Escape hatch for bespoke resolution (e.g. query an internal deploy service/CMDB API). |

Precedence: **annotation → image → catalog/tag → repoURL**. All toggleable.

---

## Configuration inputs (draft)

Collector:
- `find_command` — how to locate candidate YAML (default: repo-wide `*.yaml`/`*.yml`).
- `golden_path_label` — label/annotation marking the standard template (no default; skip template check if unset).

Cataloger (`argocd-link`):
- `correlate_by` — ordered list, e.g. `["annotation","repoURL"]` (default); add `"image"` / `"tag"` to enable those.
- `component_annotation` — annotation key for strategy 1 (default `lunar.earthly.dev/component`).
- `image_registry_aliases` — normalization map for strategy 2.
- `tag_key` — component meta/tag field for strategy 3.

Policies:
- `allowed_projects`, `allowed_source_repos`, `allowed_destinations`, `critical_tags`.

---

## Honest feasibility & risks

- **Components 1 & 2 are straightforward** and carry no platform dependencies — build them first; they deliver value standalone (validate any repo that contains ArgoCD files).
- **Correlation is best-effort, layered, not magic.** Annotation is the only fully
  reliable generic path and ideally is injected by a golden-path generator rather
  than hand-added per repo. Image-match is the best automatic booster but its
  coverage depends on how images are built and whether they're statically
  resolvable. repoURL is a weak floor in the separate-repo world.
- **`ApplicationSet`** generates `Application`s at runtime; static file parsing
  won't see them all. Out of scope for first pass; note the gap.

## Verify first (platform dependencies — deferred)

- **Rich cross-component data push** (writing `.cd.argocd` *into* another component
  rather than tags/`meta`) depends on `lunar collect --component <id> --sha <sha>`.
  Before building on it, confirm: exact flag + semantics, whether it works from a
  `code`-hook collector runtime, the auth/permission model, and — critically —
  **how to choose the target `--sha`** (the GitOps side rarely has the source
  component's HEAD sha; `targetRevision` is often a branch, not a sha). Until
  verified, the cataloger writes tags/`meta` only (sha-free).
- **API adapter** for orgs whose source of truth is a deploy service rather than
  Git — design as a separate `cron` collector that emits the same `.cd.argocd`
  schema; implement once a concrete target exists (fork-friendly).

## Out of scope (first pass)

- Argo Rollouts deep analysis beyond "present?".
- `ApplicationSet` generator expansion.
- Querying a live ArgoCD/deploy API.
- Rich cross-component JSON push.

---

## File layout

```
collectors/argocd/
  lunar-collector.yml      # code-hook parse sub-collector
  main.sh                  # parse argoproj.io/* CRDs -> .cd.argocd
policies/argocd/
  golden_path_template.py
  sync_policy.py
  non_default_project.py
  source_repo_allowlist.py
  destination_allowlist.py
  canary_for_critical.py
catalogers/argocd-link/    # phase 2
  lunar-cataloger.yml      # cron / component-cron
  main.sh                  # resolver: annotation -> image -> tag -> repoURL
```
