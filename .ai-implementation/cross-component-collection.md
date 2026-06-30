# Cross-Component Collection (out-of-band / link-push writes)

A collector usually writes Component JSON onto **its own** component. A
*cross-component* collector running on repo **A** writes onto repo **B** —
`lunar collect --component <B-id> --sha <B-sha> -j .some.path value` (the
hub's `CollectExternal` path). It's the mechanism behind the `argocd`
collector's **`link-push`** sub-collector: the ArgoCD config lives in a
separate GitOps repo, and link-push correlates each `Application` to the
**service** that builds its image and writes the deployment posture onto
*that service's* component — so the `gitops`/`argocd` policies evaluate on
the service repo, not the GitOps repo.

It's powerful and it's sharp. This doc is the field guide so the next agent
doesn't re-walk the ENG-1014 debugging gauntlet. **Read it before building
any collector that writes to a component other than its own.**

---

## Push vs Pull — pick the pattern first

This doc is about **push** (writing onto another component). There's a second
shape — **pull** (the consumer *reads* the other component's JSON) — and picking
wrong costs you a day. Decide before you build:

| | **Push** (central GitOps-repo collector, this doc) | **Pull** (app-repo collector, `get-json` self-write) |
|--|--|--|
| Direction | producer *writes* onto the target via `CollectExternal` | consumer *reads* the producer's JSON and self-writes it |
| Lands on | the target's **default-branch HEAD** (must be a real ingested SHA — gotcha #2) | the **SHA being collected** in the consumer's own run — **including a PR head SHA** |
| **Can it gate a PR?** | **No** — pushed data sits on post-merge main, not the PR's head SHA | **Yes** — that's the whole point |
| Cost | the five gotchas below (stdout hijack, SHA targeting, id-churn shadow, append/dup, self-ref) | a read perm + correlation resolved from the consumer side; **no writes** |

**Rule of thumb: PR enforcement → pull; main-branch dashboards/scoring → push.** In the
`argocd` collector they're two sub-collectors of one plugin, selected per repo with
`include`/`exclude` (see `.agents/plans/argocd-collector.md` § "One `argocd` plugin").
Everything below in *this* doc is the **push** field guide — every gotcha is a push
concern. (A policy-side SQL read was considered and dropped: policies stay fast and
node-only.)

---

## The five things that will bite you, in order

### 1. The collector runtime hijacks `lunar collect` to stdout — you MUST unset it

Inside a code-collector runtime the hub injects `LUNAR_COLLECT_STDOUT` (and
`LUNAR_LOG_PREFIX`). With those set, `lunar collect` **prints** the blob to
stdout — the runtime captures it as the *current* component's data and
**silently ignores `--component`**. Your cross-component write lands back on
the repo you're running on.

```bash
# WRONG inside a collector: --component is ignored, posture lands on self
lunar collect --component "$TARGET" --sha "$SHA" -j .cd.gitops "$blob"

# RIGHT: unset stdout-capture so it does a real hub submit
env -u LUNAR_COLLECT_STDOUT -u LUNAR_LOG_PREFIX \
    lunar collect --component "$TARGET" --sha "$SHA" -j .cd.gitops "$blob"
```

The hub connection env (`LUNAR_HUB_*`) is already present in the runtime, so
the submit authenticates fine. (Don't try to reproduce this from a laptop /
docker box outside the cluster — there's no hub conn there, so you'll get
`Hub connection details not provided` and chase a ghost. The runtime is the
only place this works.)

### 2. The target SHA must be a real, hub-ingested commit

`CollectExternal` is keyed by `(component, sha)`, and the hub **skips a SHA it
hasn't VCS-ingested** — a fabricated/unknown SHA makes the write *appear* to
succeed but the merge + policy re-eval are skipped (and logged ERROR:
`repo or commit not yet ingested`). ArgoCD `targetRevision` is usually a
branch/`HEAD`, not a SHA, so **resolve the source repo's default-branch HEAD
SHA** (GitHub API) and use that as the target. Confirm the component is
ingested at that SHA before writing.

### 3. Component IDs are NOT stable across manifest versions

This is the one that ate a full session. `component_id = StableUUID(manifest_version, name)`
in the hub — **every manifest bump reassigns every component's id.** So if you
churn the cronos manifest while testing (re-pinning a branch ref, editing
config), a component's code/CI data ends up recorded under an *old* component
id while your out-of-band write lands under the *current* id.

The symptom looks like data loss: after link-push, the target's merged JSON
shows **only the pushed paths** (`{cd}`) — its containers/vcs/sca/etc. appear
to vanish. They didn't; they're under the previous id. The hub's merge has a
`fallback_non_cron` CTE meant to carry a prior id's code/CI forward "until
collectors re-run under the new id" — **but it only fires when the current id
has *no* non-cron records, and your external write is itself a non-cron record
under the new id, so it suppresses the fallback.** (Filed as a platform
follow-up, ENG-1029.)

**`CollectExternal` merges additively by design** (there's a shipped hub test
proving a CI record + an external write at the same SHA keep both) — the
shadow is purely an artifact of manifest churn splitting the ids. **Fix for
testing/demos: stop churning the manifest. Let the source components re-collect
under the current manifest version so their code data shares the current id,
THEN run link-push so the ids align.** Then the merge is clean.

### 4. `CollectExternal` appends — it is not idempotent

Each `CollectExternal` call creates a **new** collection record (no upsert),
and the hub merge **concatenates arrays** across records at `(component, sha)`.
The hub also **auto-re-runs code collectors** (roughly once per ingested
commit anywhere in the fleet), so a cross-component array like
`.cd.gitops.applications` quietly **accumulates duplicate entries** over time
(saw it climb 1→2→…→9 with zero manual triggers). It doesn't break policies if
the dupes are identical, but the JSON isn't pristine.

Guard it collector-side: **before pushing, read the target's current state and
skip if it already carries your write.** link-push reads the target's app-name
set (where `linked_from == self`) and skips when it matches what it would push.
That held `apps: 1` across 16 consecutive hub re-runs.

> The complete fix (handle a *changed* app set + dedupe hub-side) is a platform
> change: `CollectExternal` should supersede prior external records for the same
> `(component, sha, collector)` instead of appending. Until then, the
> collector-side skip-guard is the workaround.

### 5. Guard the self-reference

A cross-component writer keys everything off `$LUNAR_COMPONENT_ID` (the repo
it's running on): the SQL lookups exclude it (so an app never resolves to its
own repo), the self-push skip, and the `linked_from` stamp. If it's ever empty,
all three break at once and you start doing garbage writes onto other
components. Given the blast radius, **bail if `$LUNAR_COMPONENT_ID` is empty**
rather than run with a broken self-ref.

---

## Reading the target's live state: use `get-json`, NOT the SQL view

The skip-guard in #4 needs the target's **current** merged JSON. Two ways to
read it, and only one is correct here:

| Source | Freshness | Use for |
|--------|-----------|---------|
| `lunar component get-json <id>` | **Immediate** — direct hub read, reflects a just-submitted external record at once | The idempotency guard, and confirming an oob write landed |
| SQL-API `components_latest` (via `lunar sql`) | **Materialized — lags by minutes** | Bulk queries / image-match lookups where staleness is tolerable |

The first idempotency-guard attempt read `components_latest` and **kept
duplicating** because the view hadn't caught up to the prior push — the guard
never saw it. Switching to `get-json` fixed it. `get-json` is also the
*authoritative* answer when the SQL view and reality disagree (it's how I
proved the "shadow" was real and not a view quirk).

---

## Cronos e2e gotchas hit while testing this

- **Brand-new repos don't auto-ingest.** The hub's GitHub App doesn't auto-cover
  a freshly-created repo, so its collections never land. Drive the test through
  an **already-ingested** repo (or get the repo registered) rather than waiting
  on a new one.
- **Don't churn the manifest mid-demo.** Every config edit / branch re-pin bumps
  the manifest version and reassigns component ids (see #3). For a clean demo:
  pin once, let everything re-collect under that version, then do your one
  sequenced run.
- **`ORDER BY timestamp` silently breaks queries against `components_latest`.**
  That SQL-API view has no `timestamp` column — ordering by it doesn't error
  loudly, it **errors to empty**, and your lookup mysteriously finds nothing.
- **Leave breadcrumbs.** link-push writes `_link_debug` (what each app resolved
  to) and `_push_debug` (`pushed_count`, per-target ok/skip) onto its own
  component JSON, because a collector's stderr isn't queryable from the hub.
  When a cross-component write "doesn't land," these tell you *why* in seconds.

---

## Collector-image / kubeconform gotchas

These bit the `argocd` collector's schema validation; they apply to any
collector baking kubeconform (the `k8s` collector hits the same surface).

- **Keep Go-template vars out of bash `${VAR:-default}` expansions.** kubeconform's
  `-schema-location` is a Go template (`{{.Group}}/{{.ResourceKind}}…`). Put it
  inside `"${LUNAR_SCHEMA:-…/{{.Group}}/…}"` and bash brace-matching eats one `}`
  → kubeconform fails registry init with `bad character U+007D`. Build the default
  with a separate `if [ -z "$VAR" ]` instead of a `:-` default.
- **Don't pass `-schema-location default`.** That location is a **remote fetch**
  (kubernetesjsonschema.dev); the collector runtime is network-restricted, so it
  hangs/fails. Bake the schemas into the image and point only at the local path.
- **datreeio CRD schema filenames are lowercase** (`application_v1alpha1.json`,
  not `Application_…`). A 404 in the image build is usually this.

---

## image-match correlation

When correlating "this app deploys image X → which component builds X", the
`correlate_by` precedence matters: **put `image` ahead of `repoURL`** if
image-match is the intended mechanism. A repoURL match (the app's source repo)
will otherwise win first and resolve the app to the GitOps repo itself instead
of the service that builds the image.

---

## TL;DR checklist for a new cross-component collector

1. `env -u LUNAR_COLLECT_STDOUT -u LUNAR_LOG_PREFIX` on the `lunar collect --component …`.
2. Target a **real ingested SHA** (resolve default-branch HEAD).
3. Don't churn the cronos manifest while testing (component ids are version-derived).
4. Make the write **idempotent** with a `get-json` skip-guard (never the SQL view).
5. **Bail if `$LUNAR_COMPONENT_ID` is empty** — don't run a cross-component writer with a broken self-ref.
