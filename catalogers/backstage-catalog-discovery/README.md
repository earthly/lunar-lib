# Backstage catalog-info.yaml Discovery Cataloger

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

1. **Tree walk.** For each repository in `repos`, the cataloger makes one recursive [Git Trees API](https://docs.github.com/en/rest/git/trees#get-a-tree) call (`GET /repos/<owner>/<repo>/git/trees/<branch>?recursive=1`) and filters the tree to blobs whose basename is in `filenames` (default `catalog-info.yaml,catalog-info.yml`). One API call finds every descriptor in the repo, regardless of nesting depth.
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

The common monorepo layout is one `catalog-info.yaml` per service directory, each declaring a single `Component` — one file, one component. A single file that declares **multiple** `Component` entities is the ambiguous case; how it should map to components (one per file vs one per entity, and how each would be keyed) is called out as an open question in the spec PR and will be documented here once decided.

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `discover` | **Scheduled.** Walks each configured repo's tree via the Git Trees API, finds every `catalog-info.yaml`, fetches and parses each, and creates one component per file keyed to the file's directory. Writes owner / domain / tags plus `.domains` stubs. Runs on a `cron` schedule. Requires `GH_TOKEN`. |

## Hook Type

| Cataloger | Hook | Schedule / Trigger | Description |
|-----------|------|--------------------|-------------|
| `discover` | `cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per run (global), scanning every repo in `repos` |

The `cron` hook is global (once per run, no repo checkout), which is what lets this cataloger *create* components — per-component hooks (`component-cron`, `component-repo`) can only augment components that already exist. Daily at 03:00 is offset from the standard `0 2 * * *` so it lands after component-defining catalogers run. Tighten the cadence by overriding `hook.schedule` in a fork.

## Installation

Add to your `lunar-config.yml` and list the repositories to scan:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-discovery@v1.0.0
    with:
      repos: "acme/monorepo,acme/platform"
```

Set the GitHub token used to walk each repo's tree and fetch each `catalog-info.yaml`:

```sh
lunar secret set GH_TOKEN <your-github-token>
```

The token needs `Contents: Read` on every repo in `repos` (`repo` scope on a classic PAT; `contents: read` on a fine-grained PAT or GitHub App installation token). Many lunar-lib plugins reuse the same `GH_TOKEN`, so if you've already set it for `github-org` or the GitHub-API collectors, this cataloger picks it up automatically. All other inputs (`filenames`, `branch`, `component_id_prefix`, `domain_annotation`, `tag_prefix`, `include_derived_tags`, `owner_format`, `default_owner`, `default_domain`) are documented in `lunar-cataloger.yml`.

### Layering With Component-Defining Catalogers

This cataloger and [`github-org`](../github-org) both *create* components, at different granularities:

- **`github-org`** creates one **repo-level** component per repository (`github.com/acme/monorepo`).
- **`backstage-catalog-discovery`** creates one component per **`catalog-info.yaml`** — for a monorepo, that's a subcomponent per service directory (`github.com/acme/monorepo/services/payments`).

Running both is the intended monorepo setup: the repo-level component plus one subcomponent per catalog-info file. For a repo with a single root `catalog-info.yaml`, this cataloger writes the same `github.com/<owner>/<repo>` id that `github-org` creates, so the two simply re-assert the same component — no conflict.

### Discovery vs the Augment Cataloger

`backstage-catalog-discovery` and [`backstage-catalog-info`](../backstage-catalog-info) are complementary, not alternatives:

| | `backstage-catalog-discovery` (this) | [`backstage-catalog-info`](../backstage-catalog-info) |
|--|--------------------------------------|-------------------------------------------------------|
| **Action** | **Creates** components | **Augments** existing components |
| **Files per repo** | Discovers **all** `catalog-info.yaml` files | Reads **one** (first configured path) |
| **Granularity** | One component per file (monorepo subcomponents) | One existing component per repo |
| **Hook** | `cron` (global — can create) | `component-cron` / `component-repo` (per-component — augment only) |

If you only need to enrich repo-level components that another cataloger already created, use `backstage-catalog-info`. If a repo holds several catalog-info files that should each become their own component, use this cataloger.

## Source System

[GitHub](https://github.com) — the cataloger calls the [Git Trees API](https://docs.github.com/en/rest/git/trees) once per configured repo to enumerate files, then the [Contents API](https://docs.github.com/en/rest/repos/contents) once per discovered `catalog-info.yaml`. Requirements:

- **`GH_TOKEN` secret** with read access to every repo in `repos`.
- **GitHub-hosted repos.** Component ids are constructed as `<component_id_prefix><owner>/<repo>[/<dir>]`; the default prefix is `github.com/`.

### Scope and Roadmap

v1 targets the **single-repo / explicit-repo-list** case that motivated it (a monorepo whose services each ship a `catalog-info.yaml`). Two extensions are noted as follow-ups rather than built here:

- **Org-wide discovery** — scan every repo in an org (or every repo already cataloged by `github-org`) instead of an explicit `repos` list.
- **Commit-triggered variant** — a checkout-based companion (mirroring `backstage-catalog-info`'s `augment-on-commit`) for near-real-time updates without the daily cron.
