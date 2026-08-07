# Backstage catalog-info.yaml Monorepo Cataloger

Discovers every `catalog-info.yaml` in a repository — including files in subdirectories — and creates one Lunar component per discovered file.

## Overview

Where the [`backstage-catalog-info`](../backstage-catalog-info) cataloger *augments components that already exist* (reading one `catalog-info.yaml` per repo), this cataloger *creates* components by discovering **all** the `catalog-info.yaml` files a repository contains and mapping each to its own Lunar component. A monorepo with `services/payments/catalog-info.yaml` and `services/web/catalog-info.yaml` becomes two components, each keyed to the file's directory and populated with the owner, domain, and tags from its Backstage `Component` entity.

It runs on a schedule, walking each configured repository's file tree via the GitHub API. Use it when a single repo holds several Backstage entities in different subdirectories and each should be its own component.

## Synced Data

This cataloger writes to the following Catalog JSON paths, once per discovered `catalog-info.yaml`:

| Path | Type | Description |
|------|------|-------------|
| `.components["<id>"]` | object | **Created** for each discovered file. `<id>` is `<component_id_prefix><owner>/<repo>` for a root file, or `<component_id_prefix><owner>/<repo>/<dir>` for a file at `<dir>/catalog-info.yaml` |
| `.components["<id>"].owner` | string | `spec.owner` of the matched Backstage `Component` (or `default_owner` fallback) |
| `.components["<id>"].domain` | string | `metadata.annotations[<domain_annotation>]` when configured and present; otherwise `spec.domain`, falling back to `spec.system`, then to `default_domain` |
| `.components["<id>"].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |
| `.domains["<domain>"]` | object | Stub entry (`{}`) for each domain a created component references, so hub catalog validation accepts the reference. When the same `catalog-info.yaml` declares a matching `kind: Domain` / `kind: System` entity, its `description` and `owner` are propagated |

The owner / domain / tag shaping is identical to the [`backstage-catalog-info`](../backstage-catalog-info) cataloger — the same inputs (`domain_annotation`, `tag_prefix`, `include_derived_tags`, `owner_format`, `default_owner`, `default_domain`) apply. The difference is that this cataloger **creates** the component keyed to the discovered file's path, rather than augmenting an existing one.

<details>
<summary>Example Catalog JSON output (a monorepo with two services)</summary>

```json
{
  "components": {
    "github.com/acme/monorepo/services/payments": {
      "owner": "group:default/team-payments",
      "domain": "platform.payments",
      "tags": ["bs-payments", "bs-type-service", "bs-lifecycle-production"]
    },
    "github.com/acme/monorepo/services/web": {
      "owner": "group:default/team-web",
      "domain": "platform.frontend",
      "tags": ["bs-frontend", "bs-type-website", "bs-lifecycle-production"]
    }
  },
  "domains": {
    "platform.payments": {
      "description": "Payments platform — billing, ledger, settlement",
      "owner": "group:default/team-payments"
    },
    "platform.frontend": {}
  }
}
```

</details>

### How Files Are Discovered and Keyed

1. **Tree walk.** For each repository in the scan set (the `repos` list plus any topic-matched repos discovered from `orgs` — see [Discovering repos by topic](#discovering-repos-by-topic)), the cataloger makes one recursive [Git Trees API](https://docs.github.com/en/rest/git/trees#get-a-tree) call (`GET /repos/<owner>/<repo>/git/trees/<branch>?recursive=1`) and filters the tree to blobs whose basename is in `filenames` (default `catalog-info.yaml,catalog-info.yml`). One API call finds every descriptor in the repo, regardless of nesting depth.
2. **Fetch + parse.** Each matched file is fetched via the Contents API (raw) and parsed (multi-document files supported).
3. **Component identity.** The created component's id is derived from the file's location:

   | File location | Component id (with default prefix) |
   |---------------|-------------------------------------|
   | `catalog-info.yaml` (repo root) | `github.com/<owner>/<repo>` |
   | `services/payments/catalog-info.yaml` | `github.com/<owner>/<repo>/services/payments` |

   The subdirectory form matches Lunar's convention for monorepo subcomponents (`github.com/acme/monorepo/service-a`), so the component's path *is* the discovered file's directory — exactly the shape a monorepo needs.

4. **Entity selection.** One component is created per discovered file. If a file declares exactly one `kind: Component`, that entity is used.

### Restricting Synced Kinds

This cataloger only creates components from `kind: Component` entities. `Domain`, `System`, `API`, `Resource`, `User`, `Group`, `Location`, etc. are ignored for component creation — a `Domain` / `System` matching a created component's domain is still read to enrich the `.domains` stub (description + owner).

### Files With Multiple Components

The common monorepo layout is one `catalog-info.yaml` per service directory, each declaring a single `Component` — one file, one component. A file that declares **zero** `Component` entities (e.g. only a `System` or `Domain`) or **more than one** `Component` is skipped, with a log line. This cataloger creates exactly one component per file and keys it to the file's directory, so it won't guess which of several `Component`s a multi-Component file maps to — give each `Component` its own directory's `catalog-info.yaml` to have it discovered. (A `Domain` / `System` alongside the single `Component` is still read to enrich the `.domains` stub.)

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `discover` | **Scheduled.** Builds a scan set from `repos` plus any topic-matched repos discovered from `orgs`, walks each repo's tree via the Git Trees API, finds every `catalog-info.yaml`, fetches and parses each, and creates one component per file keyed to the file's directory. Writes owner / domain / tags plus `.domains` stubs. Runs on a `cron` schedule. Requires `GH_TOKEN`. |

## Hook Type

| Cataloger | Hook | Schedule / Trigger | Description |
|-----------|------|--------------------|-------------|
| `discover` | `cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per run (global), scanning every repo in the scan set (`repos` plus topic-matched repos from `orgs`) |

The `cron` hook is global (once per run, no repo checkout), which is what lets this cataloger *create* components — per-component hooks (`component-cron`, `component-repo`) can only augment components that already exist. Daily at 03:00 is offset from the standard `0 2 * * *` so it lands after component-defining catalogers run. Tighten the cadence by overriding `hook.schedule` in a fork.

## Installation

Add to your `lunar-config.yml` and list the repositories to scan:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    with:
      repos: "acme/monorepo,acme/platform"
```

Set the GitHub token used to walk each repo's tree and fetch each `catalog-info.yaml`:

```sh
lunar secret set GH_TOKEN <your-github-token>
```

The token needs `Contents: Read` on every repo in `repos` (`repo` scope on a classic PAT; `contents: read` on a fine-grained PAT or GitHub App installation token). Many lunar-lib plugins reuse the same `GH_TOKEN`, so if you've already set it for `github-org` or the GitHub-API collectors, this cataloger picks it up automatically. All other inputs (`orgs`, `allowed_topics`, `disallowed_topics`, `include_archived`, `filenames`, `branch`, `exclude_paths`, `component_id_prefix`, `domain_annotation`, `tag_prefix`, `include_derived_tags`, `owner_format`, `default_owner`, `default_domain`, `allow_ignore_annotation`, `ignore_annotation`) are documented in `lunar-cataloger.yml`.

### Discovering repos by topic

Instead of hand-maintaining the `repos` list, you can auto-discover repositories across one or more organizations and opt them in by **GitHub topic**. Set `orgs` to the org(s) to scan and `allowed_topics` to the topic that marks a repo for monorepo cataloging:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    with:
      orgs: "acme"                       # discover every repo in the acme org…
      allowed_topics: "lunar-monorepo"   # …but only those tagged `lunar-monorepo`
      disallowed_topics: "no-catalog"    # …and never those tagged `no-catalog`
```

Onboarding a new monorepo is then just adding the `lunar-monorepo` topic on GitHub — no `lunar-config.yml` change.

- **`orgs`** — comma-separated org names. Every repo in each org is enumerated via the [List organization repositories API](https://docs.github.com/en/rest/repos/repos#list-organization-repositories) and added to the scan set after topic filtering. Archived repos are skipped unless `include_archived: "true"`.
- **`allowed_topics`** — when set, a discovered repo is scanned only if it carries at least one of these topics. Empty (the default) means every discovered repo passes.
- **`disallowed_topics`** — a discovered repo carrying any of these topics is skipped, even if it also matches an allowed topic (block wins over allow).

Topics are matched exactly (case-sensitive) against the repository's GitHub topics. `repos` and `orgs` can be combined — the scan set is their union — and at least one of the two must be set. **The topic filters gate only the org-discovered set; repos you name explicitly in `repos` are always scanned** (naming a repo is itself the opt-in). When using `orgs`, the `GH_TOKEN` must also be able to list the org's repositories (see [Source System](#source-system)).

### Layering With Component-Defining Catalogers

This cataloger and [`github-org`](../github-org) both *create* components, at different granularities:

- **`github-org`** creates one **repo-level** component per repository (`github.com/acme/monorepo`).
- **`backstage-catalog-info-monorepo`** creates one component per **`catalog-info.yaml`** — for a monorepo, that's a subcomponent per service directory (`github.com/acme/monorepo/services/payments`).

Running both is the intended monorepo setup: `github-org` (and/or the augment `backstage-catalog-info`) owns the repo-level component, and this cataloger adds one subcomponent per catalog-info file. By default `exclude_paths` (`catalog-info.yaml,catalog-info.yml`) excludes a root `catalog-info.yaml`, so this cataloger creates subcomponents only and never competes for the repo-level id. Clear `exclude_paths` to also map a root file to `github.com/<owner>/<repo>` when you run this cataloger on its own.

### Monorepo vs the augment cataloger

`backstage-catalog-info-monorepo` and [`backstage-catalog-info`](../backstage-catalog-info) are complementary, not alternatives:

| | `backstage-catalog-info-monorepo` (this) | [`backstage-catalog-info`](../backstage-catalog-info) |
|--|--------------------------------------|-------------------------------------------------------|
| **Action** | **Creates** components | **Augments** existing components |
| **Files per repo** | Discovers **all** `catalog-info.yaml` files | Reads **one** (first configured path) |
| **Granularity** | One component per file (monorepo subcomponents) | One existing component per repo |
| **Hook** | `cron` (global — can create) | `component-cron` / `component-repo` (per-component — augment only) |

If you only need to enrich repo-level components that another cataloger already created, use `backstage-catalog-info`. If a repo holds several catalog-info files that should each become their own component, use this cataloger.

#### Running both on the same repo

Enabling both together is the expected setup, and by default they divide cleanly with no shared writes:

- **Subdirectory files** (`services/*/catalog-info.yaml`, …) are exclusive to this cataloger. The augment cataloger only reads the first configured path (root-relative) and never descends, so it never sees them.
- **A root `catalog-info.yaml`** is left to the augment cataloger. Because `exclude_paths` defaults to `catalog-info.yaml,catalog-info.yml`, this cataloger skips the root file and only creates subcomponents — so the two never write the same component id.

If you instead run this cataloger **on its own** and want the root file to produce the repo-level component too, clear `exclude_paths`. A root file then maps to `github.com/<owner>/<repo>` — the same id the augment cataloger and `github-org` use. That's still an idempotent re-assert when they share the same transform inputs, but keeping the default `exclude_paths` alongside `backstage-catalog-info` avoids any chance of the two writing divergent values (e.g. different `tag_prefix`) to the repo-level component.

### Excluding files and components

Two mechanisms decide what does **not** become a component, at different levels of control:

- **`exclude_paths`** (platform-controlled) — a list of repo-relative paths/globs skipped before a component is ever created. It lives in `lunar-config.yml`, so dev teams can't override it. The default excludes the root `catalog-info.yaml`; add globs like `legacy/*/catalog-info.yaml` to fence off more.
- **`lunar.io/ignore` annotation** (dev-delegated, gated) — set `allow_ignore_annotation: true` and any `Component` whose `catalog-info.yaml` carries `lunar.io/ignore: "true"` (key configurable via `ignore_annotation`) opts itself out. Left off by default, so opt-out stays platform-controlled unless you choose to delegate it.

### Targeting monorepos in a mixed fleet (monorepo + polyrepo)

An org often has **both** polyrepos (one service per repo, root `catalog-info.yaml` → the repo-level component) and monorepos (many services in subdirectories, and no root component wanted). The two strategies coexist without conflict: target the monorepos explicitly and let the normal repo-level flow handle everything else.

```yaml
catalogers:
  # Repo-level components for the whole org, EXCEPT the monorepos.
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"
      exclude_repos: "big-monorepo"       # no repo-level component for the monorepo

  # Polyrepos: augment each root catalog-info onto its repo-level component.
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0

  # Monorepos: one component per subdirectory catalog-info, root excluded by default.
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    with:
      repos: "acme/big-monorepo"
```

Each polyrepo gets a repo-level component from its root `catalog-info.yaml`; the monorepo gets one component per subdirectory and **no** root component. The flows don't overlap: `github-org` excludes the monorepo, and this cataloger is scoped to it by an explicit `repos` list rather than running across every repo. (The augment cataloger harmlessly no-ops on the monorepo's subcomponents — it looks for a root file at a path that isn't a real repo and skips on the 404.) This is the "target the monorepo directly" posture; because targeting is just the `repos` list plus `github-org`'s `exclude_repos`, a fleet can mix both strategies without a one-size-fits-all cataloger.

Instead of naming each monorepo, you can flip this to **topic-driven** targeting: give this cataloger `orgs` + `allowed_topics` (e.g. tag your monorepos `lunar-monorepo`) and let `github-org` skip the same set with a matching `disallowed_topics`. Onboarding a monorepo is then a GitHub topic, not a config edit on either cataloger. See [Discovering repos by topic](#discovering-repos-by-topic).

## Source System

[GitHub](https://github.com) — when `orgs` is set the cataloger calls the [List organization repositories API](https://docs.github.com/en/rest/repos/repos#list-organization-repositories) (paged, 100/page) to enumerate candidate repos and filter them by topic; then, for every repo in the scan set, it calls the [Git Trees API](https://docs.github.com/en/rest/git/trees) once to enumerate files and the [Contents API](https://docs.github.com/en/rest/repos/contents) once per discovered `catalog-info.yaml`. Requirements:

- **`GH_TOKEN` secret** with `Contents: Read` on every repo in the scan set. When `orgs` is set, it must also be able to list the org's repositories (`read:org` / org membership for private repos, or `Metadata: Read` on a fine-grained PAT / App installation).
- **GitHub-hosted repos.** Component ids are constructed as `<component_id_prefix><owner>/<repo>[/<dir>]`; the default prefix is `github.com/`.

### Scope and Roadmap

The cataloger targets the monorepo case that motivated it (a repo whose services each ship a `catalog-info.yaml`), scoped either by an explicit `repos` list or by org discovery with a GitHub-topic allow/blocklist (see [Discovering repos by topic](#discovering-repos-by-topic)). One extension is noted as a follow-up rather than built here:

- **Commit-triggered variant** — a checkout-based companion (mirroring `backstage-catalog-info`'s `augment-on-commit`) for near-real-time updates without the daily cron.
