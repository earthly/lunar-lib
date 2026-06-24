# ArgoCD Validation Collector + GitOps Policies — Plan

A reusable GitOps guardrail set: parse and validate ArgoCD config, and (the hard
part) correlate it back to the source component when the two live in **separate
repos**. This document describes the options implemented in the **first pass**
and is explicit about what's deferred and why.

Tracking: ENG-1014.

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
   field. See "Correlation" below.

So the collector is easy; **correlating GitOps config to the right component is the
real design problem**, and we solve it with a small set of configurable strategies
plus a fork escape hatch.

---

## First-pass scope

| Phase | What | Confidence |
| -- | -- | -- |
| **1 (build now)** | `argocd` collector (parse + validate) + `gitops` policy set + correlation via **annotation** (default) and **repoURL-normalize** fallback | High — no platform dependencies |
| **2 (opt-in, same tier)** | `gitops-link` cataloger adding **image-match** and **catalog/tag** correlation strategies | Medium — depends on other collectors/catalog |
| **Deferred (verify first)** | rich cross-component data **push**, `ApplicationSet` generator resolution, **API/fork** source adapter | Blocked / needs verification |

---

## Schema: `.cd.gitops` (normalized) + `.cd.gitops.native.argocd` (raw)

A new tool-agnostic top-level category `.cd` (continuous delivery), sibling to the
existing `.ci` (continuous integration). Under it, a **methodology** level:
`.cd.gitops` holds the GitOps-specific *normalized* view — concepts that translate
across GitOps tools (a deployment unit, its sync policy, its source, its
destination, the project that scopes it). The *raw, tool-specific* shape goes under
`.cd.gitops.native.argocd`, per the established `.native.<tool>` convention.

This separates the **WHAT** (GitOps continuous delivery) from the **HOW** (ArgoCD).
A future `flux` collector populates the same `.cd.gitops.applications[]` /
`.projects[]` and writes its raw shape under `.cd.gitops.native.flux` — so the
`gitops` policy set works unchanged across tools. This mirrors the
`snyk`/`trivy`/`grype` collectors → normalized `.sca` → one `sca` policy pattern.
(Genuinely push-based CD — Spinnaker, Harness — has a different shape and would get
its own `.cd.<methodology>` sibling, not `.cd.gitops`.)

> Resolves the earlier `.cd` vs `.deployment` open question in favor of `.cd`
> (pairs symmetrically with `.ci`), per reviewer input, and pushes the tool name
> (`argocd`) down to `.native`. Neither namespace exists in
> `component-json/structure.md` yet — it will be added there once the shape is
> locked.

```jsonc
{
  "cd": {
    "gitops": {
      "source": { "tool": "argocd", "integration": "code" },
      "applications": [           // normalized: "a GitOps-managed deployment unit"
        {
          "name": "payment-api",
          "path": "apps/payment-api.yaml",
          "valid": true,                     // conforms to the argoproj CRD schema
          "kind": "Application",             // Application | ApplicationSet (Flux: Kustomization | HelmRelease)
          "project": "platform",
          "component_annotation": "github.com/org/payment-api", // lunar.earthly.dev/component, if present
          "sync_policy": { "automated": true, "prune": true, "self_heal": true },
          "destination": { "server": "...", "namespace": "payments" },
          "source_ref": { "repoURL": "https://github.com/org/gitops.git",
                          "path": "payment-api", "targetRevision": "HEAD" },
          "images": ["myregistry.io/payment-api"],   // if statically resolvable (see Correlation)
          "canary": { "rollout": true }              // Argo Rollouts referenced (data only — see Optional checks)
        }
      ],
      "projects": [
        { "name": "platform", "path": "projects/platform.yaml", "valid": true,
          "is_default": false,
          "source_repos": ["https://github.com/org/gitops.git"],
          "destinations": [{ "namespace": "payments", "server": "..." }] }
      ],
      "native": {
        "argocd": {                          // raw, ArgoCD-specific parsed resources
          "applications": [ { "path": "apps/payment-api.yaml", "resource": { /* full parsed CRD */ } } ],
          "projects":     [ { "path": "projects/platform.yaml", "resource": { /* full parsed CRD */ } } ]
        }
      }
    }
  }
}
```

Notes:

* Policies read the normalized `.cd.gitops.*` and don't care whether data came from
  ArgoCD files (now), Flux files, or an API (later).
* `images` is best-effort: only populated when the referenced workload manifests
  are plain YAML in the same repo/path. Helm/templated/generated manifests will
  often leave it empty — that's expected (see Correlation caveats).

---

## Validation (the "is there an ArgoCD linter?" answer)

There is **no single official `argocd lint` CLI** for offline manifest validation.
The standard offline approach — and the one this collector uses — is
**`kubeconform` with the argoproj CRD schemas** (from the `datreeio/CRDs-catalog`,
which publishes `argoproj.io/Application_v1alpha1.json`,
`AppProject_v1alpha1.json`, `ApplicationSet_v1alpha1.json`). This is exactly how
the existing `k8s` collector validates core resources, so it's a known, in-repo
pattern.

Each parsed resource gets a `valid` boolean (and an `error` string on failure),
and the `gitops` `valid` policy asserts every resource is schema-valid. Because
validation needs the `kubeconform` binary plus the baked CRD schemas, the collector
ships a **custom image** (`earthly/lunar-lib:argocd-main`, Earthfile added at
implementation, wired into `+all`) rather than running on `base-main`.

---

## Component 1 — `argocd` collector (parse + validate)

A `code`-hook collector that scans the cloned repo for ArgoCD CRDs
(`apiVersion: argoproj.io/*`), validates each against the argoproj schemas, and
writes the normalized `.cd.gitops` view above (plus raw `.cd.gitops.native.argocd`)
to its **own** Component JSON. Works in both modes with no special handling:

* a dedicated GitOps/ArgoCD repo (finds many `Application`s), and
* a component repo that ships its own ArgoCD files (finds its own).

Composes with the existing `k8s` and `docker` collectors (it does not re-parse
workloads — it references them).

---

## Component 2 — `gitops` policy set

Tool-agnostic checks over `.cd.gitops` (one check per file, `include`/`exclude`-able).
All resolve to **skip** when `.cd.gitops` is absent (no GitOps config in this
component), per the skip-vs-fail convention. The default set is intentionally lean
and **general — it applies to essentially any team running ArgoCD**, with nothing
tied to a specific customer's platform conventions:

* `valid` — every Application/AppProject conforms to the argoproj CRD schema.
* `sync-policy` — `syncPolicy.automated` with `prune` + `selfHeal` true.
* `non-default-project` — `spec.project` is not `default` (and, optionally, within an allow-list).
* `source-repo-allowlist` — `source.repoURL` within configured allowed repos (allow-list: errors if enabled but unconfigured).
* `destination-allowlist` — destination namespace/cluster within allow-list (allow-list: errors if enabled but unconfigured).

### Optional checks (niche — NOT in the default set)

These two came out of the originating design session's specific platform use-case.
They're real, but they are **not general** to most ArgoCD users, so they're kept
out of the shipped default set and offered as opt-in additions (or a later phase)
only if there's demand. The underlying *data* is still collected where it's
generally useful.

* `golden-path-template` — asserts each Application carries an org-specific
  "golden-path" template label. This is a **platform-engineering pattern** (a
  golden-path manifest generator stamps the label), not something most ArgoCD users
  do. Opt-in: the collector can extract a configured label, and a future policy can
  enforce it, but it's off by default.
* `canary-for-critical` — asserts critical-tier components deploy via canary. Note
  **Argo Rollouts is a *separate* argoproj project** (its own `Rollout` CRD), not
  part of core ArgoCD — and mandating progressive delivery is a strong stance. The
  collector still records `.canary.rollout` (whether an Application references a
  Rollout) as general adoption-visibility data; the *mandate* is deferred/opt-in.

---

## Component 3 — Cross-component correlation (`gitops-link` cataloger) — Phase 2

When the GitOps files and the source component are different repos, we need to
attach the deployment posture (or at least a link) to the **source component**.

Mechanism: a **cataloger** (catalogers can write tags/`meta` to *other*
components, and aren't sha-keyed). It reads the GitOps repo's `.cd.gitops`,
resolves each `Application` to a component, and stamps the target component with a
tag (`gitops-managed`) and `meta` (e.g. `gitops_app`, `gitops_project`, sync-policy
booleans). Policies on the source component then read those.

### Correlation strategies (configurable, first-match-wins)

| # | Strategy | Where the key lives | Default | Requires | Honest coverage |
| -- | -- | -- | -- | -- | -- |
| 1 | **Annotation** | producer: an annotation on the `Application` (e.g. `lunar.earthly.dev/component: github.com/org/app`) | ✅ on | a convention (best injected once by a golden-path generator) | Deterministic. Not a pre-existing industry standard, but cheap to adopt and the most reliable. |
| 2 | **Image match** | natural key: `Application` deployed image ↔ component's built image (`.containers.builds[].image` from the `docker` collector) | opt-in input | `docker` collector enabled + image statically resolvable | Best *automatic* path. Misses jib/Bazel/ko/Kaniko builds and templated images; needs registry normalization. |
| 3 | **Catalog / tag** | consumer: component carries a tag/`meta` mapping (often from an existing catalog) | opt-in input | a source of truth (e.g. Backstage `source-location`, ingested by the `backstage` collector) | Strong for catalog-mature orgs. Not a bootstrap method — needs the mapping to already exist. |
| 4 | **repoURL normalize** | natural key: normalize `source.repoURL` → component id | ✅ fallback | nothing | Only correct when manifests are co-located with source or the GitOps repo *is* the target. Weak in the separate-repo case. |
| — | **Fork** | custom | n/a | code change | Escape hatch for bespoke resolution (e.g. query an internal deploy service/CMDB API). |

Precedence: **annotation → image → catalog/tag → repoURL**. All toggleable.

Phase 1 ships the annotation extraction (`.cd.gitops.applications[].component_annotation`)
and the repoURL data (`.cd.gitops.applications[].source_ref.repoURL`) inside the
collector so the cataloger has both ends to work with when it lands.

---

## Configuration inputs

Collector:

* `find_command` — how to locate candidate YAML (default: repo-wide `*.yaml`/`*.yml`).

Cataloger (`gitops-link`, Phase 2):

* `correlate_by` — ordered list, e.g. `["annotation","repoURL"]` (default); add `"image"` / `"tag"` to enable those.
* `component_annotation` — annotation key for strategy 1 (default `lunar.earthly.dev/component`).
* `image_registry_aliases` — normalization map for strategy 2.
* `tag_key` — component meta/tag field for strategy 3.

Policies (`gitops`):

* `allowed_projects`, `allowed_source_repos`, `allowed_destinations`.

---

## Honest feasibility & risks

* **Components 1 & 2 are straightforward** and carry no platform dependencies — build them first; they deliver value standalone (validate any repo that contains ArgoCD files).
* **Correlation is best-effort, layered, not magic.** Annotation is the only fully
  reliable generic path and ideally is injected by a golden-path generator rather
  than hand-added per repo. Image-match is the best automatic booster but its
  coverage depends on how images are built and whether they're statically
  resolvable. repoURL is a weak floor in the separate-repo world.
* `ApplicationSet` generates `Application`s at runtime; static file parsing
  won't see them all. Out of scope for first pass; note the gap.

## Verify first (platform dependencies — deferred)

* **Rich cross-component data push** (writing `.cd.gitops` *into* another component
  rather than tags/`meta`) depends on `lunar collect --component <id> --sha <sha>`.
  Before building on it, confirm: exact flag + semantics, whether it works from a
  `code`-hook collector runtime, the auth/permission model, and — critically —
  **how to choose the target** `--sha` (the GitOps side rarely has the source
  component's HEAD sha; `targetRevision` is often a branch, not a sha). Until
  verified, the cataloger writes tags/`meta` only (sha-free).
* **API adapter** for orgs whose source of truth is a deploy service rather than
  Git — design as a separate `cron` collector that emits the same `.cd.gitops`
  schema; implement once a concrete target exists (fork-friendly).

## Out of scope (first pass)

* Argo Rollouts deep analysis beyond "present?".
* `ApplicationSet` generator expansion.
* Querying a live ArgoCD/deploy API.
* Rich cross-component JSON push.

---

## File layout

```
collectors/argocd/
  lunar-collector.yml      # code-hook parse + validate sub-collector
  main.sh                  # parse + kubeconform-validate argoproj.io/* CRDs -> .cd.gitops
  Earthfile                # custom image: kubeconform + argoproj CRD schemas
policies/gitops/
  valid.py
  sync_policy.py
  non_default_project.py
  source_repo_allowlist.py
  destination_allowlist.py
catalogers/gitops-link/    # phase 2
  lunar-cataloger.yml      # cron / component-cron
  main.sh                  # resolver: annotation -> image -> tag -> repoURL
```
