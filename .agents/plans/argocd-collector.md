# ArgoCD Validation Collector + GitOps Policies — Plan

A reusable GitOps guardrail set: parse and validate ArgoCD config, enforce GitOps
best practices, and — the hard part — **push the deployment posture back onto the
source component** when the ArgoCD config and the application source live in
**separate repos**. Everything below ships in **one PR** (ENG-1014 / #218).

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

So the collector is easy; **correlating GitOps config to the right component, and
attaching its deployment posture there, is the real design problem.** We solve it
with a small set of configurable correlation strategies plus the out-of-band
collect syntax to write the result onto the source component.

---

## Scope — all in this PR

| Piece | What | Confidence |
| -- | -- | -- |
| `argocd` collector — `parse` sub-collector | parse + kubeconform-validate argoproj CRDs → normalized `.cd.gitops` + raw `.cd.gitops.native.argocd` on the GitOps repo's own component | High — no platform deps |
| `gitops` policy set | 5 tool-agnostic checks over `.cd.gitops` | High — no platform deps |
| `argocd` collector — `link-push` sub-collector | resolve each Application → source component (annotation → image → tag → repoURL), then **out-of-band `lunar collect --component <source-id> --sha <sha>`** to write the deployment posture onto the **source** component | Medium — depends on ENG-859 out-of-band collect (shipped on `earthly/lunar` main); a few things to confirm at impl (below) |

Genuinely out of scope (not asked for, real gaps): `ApplicationSet` runtime
generator expansion, and a live ArgoCD/deploy-service **API adapter** (a future
`cron` collector emitting the same `.cd.gitops` schema — fork-friendly).

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

When `link-push` writes onto a **source** component, it writes the single matched
application plus a link marker so policies/dashboards can tell it came in
out-of-band:

```jsonc
{
  "cd": {
    "gitops": {
      "source": { "tool": "argocd", "integration": "external" },   // pushed, not parsed locally
      "linked_from": "github.com/org/gitops",                       // the GitOps repo it was resolved from
      "applications": [ { "name": "payment-api", "project": "platform",
                          "sync_policy": { "automated": true, "prune": true, "self_heal": true },
                          "destination": { "namespace": "payments" }, "...": "..." } ]
    }
  }
}
```

Notes:

* Policies read the normalized `.cd.gitops.*` and don't care whether the data was
  parsed locally (GitOps repo) or pushed in out-of-band (source repo).
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

## Component 1 — `argocd` collector, `parse` sub-collector (parse + validate)

A `code`-hook sub-collector that scans the cloned repo for ArgoCD CRDs
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
* `gitops-managed` — **coverage** check (see Component 4): fails a component that *should* be on GitOps but has no resolved `.cd.gitops`.

Because `link-push` (Component 3) writes `.cd.gitops` onto the **source** component
too, these policies light up on the service repo — not just the GitOps repo — even
when ArgoCD config lives elsewhere.

### Optional checks (niche — NOT in the default set)

These two came out of the originating design session's specific platform use-case.
They're real, but they are **not general** to most ArgoCD users, so they're kept
out of the shipped default set and offered as opt-in additions (or a later phase)
only if there's demand. The underlying *data* is still collected where it's
generally useful.

* `golden-path-template` — asserts each Application carries an org-specific
  "golden-path" template label. A **platform-engineering pattern** (a golden-path
  manifest generator stamps the label), not something most ArgoCD users do.
* `canary-for-critical` — asserts critical-tier components deploy via canary. Note
  **Argo Rollouts is a *separate* argoproj project** (its own `Rollout` CRD), not
  part of core ArgoCD — and mandating progressive delivery is a strong stance. The
  collector still records `.canary.rollout` as adoption-visibility data; the
  *mandate* is deferred/opt-in.

---

## Component 3 — `argocd` collector, `link-push` sub-collector (cross-component out-of-band push)

This is the piece that makes GitOps guardrails work in the **separate-repo** world:
attach each Application's deployment posture to the **source component** it deploys,
even though the ArgoCD config lives in a different repo.

Mechanism — a `code`-hook sub-collector that runs on the **GitOps** repo:

1. Reads the parsed `.cd.gitops.applications[]` (from the `parse` step).
2. **Resolves each Application → source component id** via the strategy chain below
   (first match wins): `annotation → image → catalog/tag → repoURL`.
3. **Resolves the source component's target SHA** — the default-branch HEAD sha of
   the source repo (see "to confirm" below; this must be a commit the Hub has
   already VCS-ingested).
4. **Writes out-of-band** with the ENG-859 syntax:
   ```bash
   lunar collect --component "$SOURCE_ID" --sha "$SOURCE_SHA" -j \
     ".cd.gitops.applications" "[ { ...matched application... } ]" \
     ".cd.gitops.source"      '{"tool":"argocd","integration":"external"}' \
     ".cd.gitops.linked_from" "\"$GITOPS_COMPONENT_ID\""
   ```
   The Hub stores this as an `external` collection keyed by `(source component, sha)`
   and **re-evaluates that SHA's policies** — so the source component's `gitops`
   checks (and dashboards) reflect its ArgoCD posture immediately.

### Correlation strategies (configurable, first-match-wins)

| # | Strategy | Where the key lives | Default | Requires | Honest coverage |
| -- | -- | -- | -- | -- | -- |
| 1 | **Annotation** | producer: an annotation on the `Application` (e.g. `lunar.earthly.dev/component: github.com/org/app`) | ✅ on | a convention (best injected once by a golden-path generator) | Deterministic. Not a pre-existing industry standard, but cheap to adopt and the most reliable. |
| 2 | **Image match** | natural key: `Application` deployed image ↔ component's built image (`.containers.builds[].image` from the `docker` collector) | opt-in input | `docker` collector enabled + image statically resolvable | Best *automatic* path. Misses jib/Bazel/ko/Kaniko builds and templated images; needs registry normalization. |
| 3 | **Catalog / tag** | consumer: component carries a tag/`meta` mapping (often from an existing catalog) | opt-in input | a source of truth (e.g. Backstage `source-location`, ingested by the `backstage` collector) | Strong for catalog-mature orgs. Not a bootstrap method — needs the mapping to already exist. |
| 4 | **repoURL normalize** | natural key: normalize `source.repoURL` → component id | ✅ fallback | nothing | Only correct when manifests are co-located with source or the GitOps repo *is* the target. Weak in the separate-repo case. |
| — | **Fork** | custom | n/a | code change | Escape hatch for bespoke resolution (e.g. query an internal deploy service/CMDB API). |

Precedence: **annotation → image → catalog/tag → repoURL**. All toggleable. The
sub-collector logs which strategy resolved each link, and skips (with a logged
reason) any Application it can't resolve — no bogus writes.

### To confirm at implementation (the load-bearing details)

The out-of-band collect syntax is **shipped on `earthly/lunar` main** (ENG-859):
`lunar collect --component <id> --sha <sha> …` submits an `external` collection via
the `CollectExternal` RPC and triggers a re-eval for that SHA. Three things to nail
down during implementation/cronos e2e:

1. **Target SHA must be Hub-ingested.** Out-of-band collect lands at `(component,
   sha)` and the Hub silently skips a SHA it hasn't VCS-ingested. ArgoCD
   `targetRevision` is usually a branch (`HEAD`) or tag, not a sha — so `link-push`
   resolves the **source repo's default-branch HEAD sha** (GitHub API) as the
   target, which is the commit the Hub most likely has. Confirm on cronos that the
   write lands and re-eval fires; if the Hub exposes a "latest ingested sha for
   component X" lookup, prefer that over the GitHub API.
2. **CLI version.** `--component/--sha` must be present in the `lunar` baked into
   the collector image. It's on `earthly/lunar` main; confirm the image's CLI has
   it before cronos e2e.
3. **Permission model.** Confirm the collector's Hub token is allowed to write a
   collection to a **different** component (cross-component `CollectExternal`).

Until #1–#3 are confirmed green on cronos, `parse` + `gitops` policies ship
standalone (they have no such dependency); `link-push` is the same PR's second
unit and gates the PR's "ready" flip on its e2e.

---

## Component 4 — GitOps adoption coverage (`gitops-managed`)

Three connected questions a link-pushed component should be able to answer:

**1. Do the policies run *gracefully* on a link-pushed component?** Yes — that's the
whole point of `link-push`. The pushed record carries the *full* normalized
application shape (`valid`, `sync_policy`, `project`, `destination`, `source_ref`),
so the five config checks evaluate on the source component exactly as they would on
the GitOps repo. The component needs no local ArgoCD files. One edge case: if the
source component *also* ships its own ArgoCD files, its local `.cd.gitops` and the
pushed `.cd.gitops` merge (Hub array-concat) — `link-push` dedupes by application
name so the same app doesn't appear twice.

**2. Positive signal — "is this component on ArgoCD?"** Presence of `.cd.gitops` on
the component *is* the signal (object-presence convention — no redundant
`managed: true` boolean). `.cd.gitops.source.integration` distinguishes how it got
there: `code` (the component ships its own ArgoCD files) vs `external` (link-pushed
from a separate GitOps repo). So "which components are on ArgoCD" is a simple
presence query across the fleet — exactly the visibility orgs lack mid-migration.

**3. The hard inverse — "which components *should* be on ArgoCD but aren't?"** This
is the migration-coverage gap, and it can't come from the GitOps config alone (the
un-migrated components are, by definition, absent from it). It has to come from the
**expected-deployment signal on the component side** — i.e. component tags /
cataloging. The `gitops-managed` check encodes it:

* Applied to the components you expect on GitOps (via lunar-config `on:` targeting —
  "applying the policy to the correct deployment", as you put it — and/or an
  optional `expected_tag` filter), it asserts `.cd.gitops` **exists**.
* Absent → **FAIL** ("expected to be GitOps-managed but no ArgoCD Application
  deploys it"). This is the inverse skip-vs-fail of the config checks: there,
  absence = skip (vendor not in use); here, absence = the violation. The user
  opted in by tagging/targeting, so absence is a real finding.
* A component *not* in the expected set (lacks the tag / outside the `on:` scope)
  → **skip**.

The expected-on-GitOps set is the org's own input (a tag like `should-be-gitops`,
set by hand or by a cataloger such as `backstage`). Lunar doesn't invent it — it
just enforces coverage against it.

**Convergence note:** `gitops-managed` reads `.cd.gitops` presence, which for a
separate-repo component arrives via `link-push`'s out-of-band write (and the write
triggers a re-eval for that SHA). So a freshly-onboarded org may see transient
failures that resolve as the `argocd` collector processes the GitOps repo and the
links land — eventual consistency, not a false negative.

---

## Configuration inputs

Collector (`argocd`):

* `find_command` — how to locate candidate YAML (default: repo-wide `*.yaml`/`*.yml`). *(parse)*
* `correlate_by` — ordered strategy list, e.g. `["annotation","repoURL"]` (default); add `"image"` / `"tag"` to enable those. *(link-push)*
* `component_annotation` — annotation key for strategy 1 (default `lunar.earthly.dev/component`). *(link-push)*
* `image_registry_aliases` — registry normalization map for strategy 2. *(link-push)*
* `tag_key` — component meta/tag field for strategy 3. *(link-push)*

Secret (`link-push`): a GitHub token to resolve each source repo's default-branch
HEAD sha (target for the out-of-band write).

Policies (`gitops`):

* `allowed_projects`, `allowed_source_repos`, `allowed_destinations` *(config checks)*.
* `expected_tag` — for `gitops-managed`: only enforce coverage on components carrying this tag (empty = every targeted component).

---

## Honest feasibility & risks

* **`parse` + `gitops` policies are straightforward** and carry no platform
  dependencies — they deliver value standalone (validate any repo with ArgoCD files).
* **`link-push` is the dependent piece.** The out-of-band write itself is shipped
  (ENG-859); the open work is target-SHA selection, image CLI version, and the
  cross-component permission model (see "To confirm" above). All three are
  cronos-verifiable in this PR.
* **Correlation is best-effort, layered, not magic.** Annotation is the only fully
  reliable generic path and ideally is injected by a golden-path generator rather
  than hand-added per repo. Image-match is the best automatic booster but its
  coverage depends on how images are built and whether they're statically
  resolvable. repoURL is a weak floor in the separate-repo world.
* `ApplicationSet` generates `Application`s at runtime; static file parsing
  won't see them all — noted gap, out of scope.

## Out of scope (this PR)

* Argo Rollouts deep analysis beyond "present?".
* `ApplicationSet` generator expansion.
* Querying a live ArgoCD/deploy API (future `cron` collector emitting `.cd.gitops`).

---

## File layout

```
collectors/argocd/
  lunar-collector.yml      # parse (code) + link-push (code) sub-collectors
  main.sh                  # parse + kubeconform-validate argoproj.io/* CRDs -> .cd.gitops
  link_push.sh             # resolve Application -> source component, out-of-band lunar collect --component/--sha
  Earthfile                # custom image: kubeconform + argoproj CRD schemas
policies/gitops/
  valid.py
  sync_policy.py
  non_default_project.py
  source_repo_allowlist.py
  destination_allowlist.py
  gitops_managed.py        # coverage: fails components expected on GitOps but absent
```
