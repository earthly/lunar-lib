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
| `gitops` policy set (general) + `argocd` policy set (specific) | tool-agnostic checks over `.cd.gitops` + ArgoCD-specific checks (argoproj CRD validation, AppProject) | High — no platform deps |
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

## Component 2 — Two policy plugins: `gitops` (general) + `argocd` (specific)

The checks split cleanly by *what they depend on*, so they ship as **two policy
plugins** — same pattern as the repo's existing `policies/iac` (general) +
`policies/terraform` (tool-specific), both fed by one `terraform` collector. Here,
one `argocd` collector feeds both `policies/gitops` and `policies/argocd`; a future
`flux` collector would also feed `policies/gitops`.

**Dividing line:** a check is **general** iff it reads only normalized, tool-
agnostic `.cd.gitops` fields any GitOps collector populates. It's **ArgoCD-specific**
iff it depends on an ArgoCD concept (AppProject) or argo-schema validation.

### `policies/gitops` — tool-agnostic (works for ArgoCD, Flux, …)

Reads only normalized `.cd.gitops`. All resolve to **skip** when `.cd.gitops` is
absent — except `gitops-managed`, which inverts that (see Component 4).

* `sync-policy` — `sync_policy.automated` with `prune` + `self_heal` true (normalized; a Flux collector maps its reconcile/prune fields to the same shape).
* `source-repo-allowlist` — `source_ref.repoURL` within configured allowed repos (allow-list: errors if enabled but unconfigured).
* `destination-allowlist` — `destination` namespace/cluster within allow-list (allow-list: errors if enabled but unconfigured).
* `gitops-managed` — **coverage** check (Component 4): fails a component that *should* be on GitOps but has no resolved `.cd.gitops`.

### `policies/argocd` — ArgoCD-specific (argoproj CRDs / AppProject)

* `valid` — every Application/ApplicationSet/AppProject conforms to the **argoproj CRD schema** (Flux has different CRDs → a `flux` policy would have its own `valid`).
* `non-default-project` — `spec.project` is not `default` (and, optionally, within an allow-list). **AppProject is an ArgoCD concept** — Flux has no equivalent.

Because `link-push` (Component 3) writes `.cd.gitops` onto the **source** component
too, both policy sets light up on the service repo — not just the GitOps repo —
even when ArgoCD config lives elsewhere.

### Optional checks (niche — NOT shipped, would live under `policies/argocd`)

These two came out of the originating design session's specific platform use-case.
They're real but **not general**, so they're kept out of the shipped set and
offered as opt-in additions only if there's demand. The underlying *data* is still
collected where it's generally useful.

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

## One `argocd` plugin: `parse` + two correlation sub-collectors

ArgoCD config can live **with the service** (the repo ships its own `Application`) or in
a **separate central GitOps repo**. To make the `gitops`/`argocd` policies evaluate on
the **service** either way, the `argocd` collector carries two correlation sub-collectors
alongside `parse`. Both feed the **same** normalized `.cd.gitops` and the **same**
policies — two correlation front-ends, not duplicated policy surface.

**One plugin, gated by `include`/`exclude`** *(per review — Brandon)*. Lib collectors
group by *technology* and let the user select sub-collectors per repo with
`include`/`exclude`; that mechanism already covers "different repos run different
sub-collectors," so this stays a single `argocd` plugin rather than two. The central
GitOps repo includes `parse` + the push sub-collector; an app/service repo includes the
pull one (+ `parse` if it ships local Argo files).

The distinction (Vlad's framing — past vs future):

- **Currently deployed (push).** Runs on the **central GitOps repo**: correlates each
  `Application` to the **service it deploys** (image-match) and records that deployed
  posture onto the service via out-of-band `CollectExternal`. It writes at the service's
  *default-branch HEAD* (it must — the Hub drops a SHA it hasn't ingested, Component 3
  gotcha #2), so it describes **post-merge main only**. It **cannot** gate a PR; it
  answers "what is deployed, and which source repo built it."
- **Going to be deployed (pull).** Runs on each **app/service repo**: `get-json`s this
  service's `Application` from the GitOps component and materializes `.cd.gitops` onto
  the service at the SHA being collected — **including a PR head SHA** — so the policies
  enforce "does this change fit the deployment requirements" **at PR time**.

### The two sub-collectors

| Sub-collector | Runs on | Job | Today's code |
| -- | -- | -- | -- |
| **`push-deployed-state`** | central **GitOps repo** | correlate each `Application` → the service it deploys, record the deployed posture onto that service (out-of-band) | `link_push.sh` |
| **`pull-deployment-readiness`** | each **app / service repo** | `get-json` this service's `Application` from the GitOps component and self-write `.cd.gitops` at the collected SHA, so PR checks validate the upcoming deployment | `link_pull.sh` |

> **Naming — converging, pending Vlad.** Both reviewers agree the bare
> `link-push`/`link-pull` names leak our implementation mental-model. Brandon's proposal
> keeps `push`/`pull` as a *locational* prefix (it says where the sub-collector runs)
> **paired with the outcome**: `push-deployed-state` / `pull-deployment-readiness`.
> Vlad's earlier note wanted push/pull *out* of the user-facing name entirely — so the
> prefix is his call to bless. Pure-outcome fallbacks if he'd rather drop it:
> `deployed-state` / `deployment-readiness`.

### Don't enable both on the same service — pick one

Both write `.cd.gitops.applications`. If a service is **both** push-targeted (by the
GitOps repo) **and** runs pull, both land at the same `(component, sha)` and the Hub
**concatenates** the two collection records (it appends, never upserts) → the same
`Application` appears **twice**. Policy *verdicts* don't flip (identical entries → same
pass/fail), but coverage **counts double** and the two entries can **transiently
disagree** (push = currently-deployed, pull = declared-at-this-SHA). So the guidance is
**one per service**: push for zero-config post-merge correlation/dashboards (no PR
gate); pull for PR-time enforcement (costs a `catalog-info` mapping). The push
skip-guard only dedupes push-vs-push, so it won't catch a push+pull overlap — a proper
fix is platform-side (supersede external records instead of appending).

> **Decision pending (Vlad).** (1) One plugin + `include`/`exclude` *(recommended —
> matches lib convention)* vs two separate plugins *(Vlad's original ask)*; (2) keep the
> `push`/`pull` prefix in the sub-collector names *(Brandon: yes, it's locational)* vs
> pure-outcome names *(Vlad's earlier note)*. I rename structure + sub-collectors in one
> pass once these land.

### Pull is a collector read, NOT an in-policy SQL query

An earlier sketch had a "Strategy-3" variant where the **policy** queried the Lunar SQL
API directly at eval time. **Dropped (per Vlad):** the platform assumes policies are
fast and self-contained, and there's no supported in-policy SQL pattern yet. The pull
sub-collector does a normal `get-json` self-write; the policies read `.cd.gitops`
unchanged and stay node-only. Revisit a policy-side read only if/when the platform grows
a first-class pattern for it.

The pull sub-collector avoids every push-side gotcha — no `CollectExternal`, no
SHA-targeting, no append/dup guard, no manifest-id shadow, no cross-component *write*
permission. It's a self-write on the SHA being collected.

### To confirm at implementation (pull)

1. **`get-json` perms/cost** — confirm an app-repo collector may `get-json` a *different*
   component (read perm) cheaply each collection. Read is lower-privilege than push's
   cross-component *write*.
2. **App-side correlation** — pull resolves service→its GitOps `Application` from the
   *app* side, via a predeclared `catalog-info.yaml` mapping
   (`lunar.earthly.dev/gitops-component` + `lunar.earthly.dev/argocd-application`), or a
   direct `gitops_component` input. (Docker-image auto-correlation would need the build
   collector to have run first — a collector-ordering dep we don't have yet.)

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

Policies (`gitops`, general):

* `allowed_source_repos`, `allowed_destinations` *(allow-list config checks)*.
* `expected_tag` — for `gitops-managed`: only enforce coverage on components carrying this tag (empty = every targeted component).

Policies (`argocd`, specific):

* `allowed_projects` — for `non-default-project`: optional AppProject allow-list.

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
  lunar-collector.yml      # parse + push-deployed-state + pull-deployment-readiness sub-collectors (all code hooks)
  main.sh                  # parse: kubeconform-validate argoproj.io/* CRDs -> .cd.gitops
  link_push.sh             # push-deployed-state: resolve Application -> source component, out-of-band lunar collect --component/--sha
  link_pull.sh             # pull-deployment-readiness: get-json this service's Application from the GitOps component, self-write .cd.gitops
  Earthfile                # custom image: kubeconform + argoproj CRD schemas
policies/gitops/           # tool-agnostic (any GitOps tool); reads normalized .cd.gitops
  sync_policy.py
  source_repo_allowlist.py
  destination_allowlist.py
  gitops_managed.py        # coverage: fails components expected on GitOps but absent
policies/argocd/           # ArgoCD-specific (argoproj CRDs / AppProject)
  valid.py                 # argoproj CRD schema validation
  non_default_project.py   # AppProject hygiene
```
