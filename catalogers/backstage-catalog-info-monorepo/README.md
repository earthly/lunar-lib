# Backstage catalog-info.yaml Monorepo Cataloger

Discovers every `catalog-info.yaml` in a repository — including files in subdirectories — and creates one Lunar component per discovered file.

## Overview

Where the [`backstage-catalog-info`](../backstage-catalog-info) cataloger *augments components that already exist* (reading one `catalog-info.yaml` per repo), this cataloger *creates* components by discovering **all** the `catalog-info.yaml` files a repository contains and mapping each to its own Lunar component. A monorepo with `services/payments/catalog-info.yaml` and `services/web/catalog-info.yaml` becomes two components, each keyed to the file's directory and populated with the owner, domain, and tags from its Backstage `Component` entity.

It runs daily, and optionally on every push to a monorepo, walking each repository's file tree via the GitHub API. Use it when a single repo holds several Backstage entities in different subdirectories and each should be its own component.

## Synced Data

This cataloger writes to the following Catalog JSON paths, once per discovered `catalog-info.yaml`:

| Path | Type | Description |
|------|------|-------------|
| `.components["<id>"]` | object | **Created** for each discovered file. `<id>` is `<component_id_prefix><owner>/<repo>` for a root file, or `<component_id_prefix><owner>/<repo>/<dir>` for a file at `<dir>/catalog-info.yaml` |
| `.components["<id>"].owner` | string | `spec.owner` of the matched Backstage `Component` (or `default_owner` fallback) |
| `.components["<id>"].domain` | string | `metadata.annotations[<domain_annotation>]` when configured and present; otherwise `spec.domain`, falling back to `spec.system`, then to `default_domain`. A `spec.domain` / `spec.system` that names a `Domain` / `System` declared anywhere in the scanned files resolves to its full dotted path — see [Domain Hierarchy](#domain-hierarchy) |
| `.components["<id>"].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |
| `.domains["<domain>"]` | object | One row per `Domain` / `System` entity declared in the scanned files, keyed by its dotted path, with its `description` and `owner`. Any other domain a created component references gets an empty stub (`{}`), so hub catalog validation accepts the reference |

The owner / tag shaping and the `domain_annotation`, `tag_prefix`, `include_derived_tags`, `owner_format`, `default_owner` and `default_domain` inputs match the [`backstage-catalog-info`](../backstage-catalog-info) cataloger. The differences: this cataloger **creates** the component keyed to the discovered file's path, and it resolves the Domain / System hierarchy across every file it scans, not just the Component's own file.

<details>
<summary>Example Catalog JSON output (the monorepo in <a href="#domain-hierarchy">Domain Hierarchy</a>)</summary>

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
    "platform": {
      "description": "Platform engineering",
      "owner": "group:default/team-platform"
    },
    "platform.payments": {
      "description": "Payments platform — billing, ledger, settlement",
      "owner": "group:default/team-payments"
    },
    "platform.frontend": {
      "owner": "group:default/team-web"
    }
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

### Domain Hierarchy

Backstage nests by reference: a `Component` names its `spec.system`, a `System` names its `spec.domain`, and a `Domain` names its parent with `spec.subdomainOf`. Lunar nests by name: `a.b.c` is a child of `a.b`. Before creating any component, the cataloger reads every `Domain` and `System` entity in the files listed below, then resolves each Component's `spec.system` (or `spec.domain`) to the full dotted path. A policy on `domain:platform` then applies to everything under `platform.payments`.

The System and Domain entities don't have to sit in the Component's file. With this layout:

```yaml
# catalog-info.yaml (repo root: excluded from component creation by default, still read for the hierarchy)
kind: Domain
metadata: { name: platform, description: Platform engineering }
spec: { owner: group:default/team-platform }
---
kind: System
metadata: { name: payments, description: "Payments platform — billing, ledger, settlement" }
spec: { owner: group:default/team-payments, domain: platform }
---
kind: System
metadata: { name: frontend }
spec: { owner: group:default/team-web, domain: platform }

# services/payments/catalog-info.yaml
kind: Component
metadata: { name: payment-api, tags: [payments] }
spec: { type: service, lifecycle: production, owner: group:default/team-payments, system: payments }

# services/web/catalog-info.yaml
kind: Component
metadata: { name: web-app, tags: [frontend] }
spec: { type: website, lifecycle: production, owner: group:default/team-web, system: frontend }
```

`payment-api` lands in `platform.payments` and `web-app` in `platform.frontend`, with a `.domains` row for `platform`, `platform.payments` and `platform.frontend` (the example output above).

Where the hierarchy is read from:

- **Every catalog-info file in the scan set**, including files that don't become components: files matched by `exclude_paths`, and files without exactly one `Component` (a file of only `System` / `Domain` entities, say).
- **`hierarchy_paths`**: path globs for System / Domain YAML with other names, such as `catalog/domains/*.yaml`. Matched like `exclude_paths`, against the full repo-relative path in the scanned repos and `hierarchy_repos` (`*` also matches `/`). Files matched only by `hierarchy_paths` never become components.
- **`hierarchy_repos`**: repos read only for System / Domain entities, never for components, always from their default branch. Use it for a central catalog repo:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    include: [discover, discover-on-commit]
    with:
      repos: "acme/monorepo"
      hierarchy_repos: "acme/software-catalog"
      hierarchy_paths: "domains/*.yaml,systems/*.yaml"
```

Resolution rules:

- `domain_annotation` and `default_domain` values are used as written, never resolved.
- A parent that isn't declared in any file the cataloger reads contributes its bare name and stops the walk. A System under an undeclared `developer-platform` resolves to `developer-platform.build-tools`, so declare the whole chain.
- A name declared twice with different parents logs a warning, and the last file read wins.
- Entity refs such as `domain:default/platform` resolve by name. `kind: Location` targets aren't followed, so point `hierarchy_paths` at the files they list.
- A push to a `hierarchy_repos` repo doesn't trigger `discover-on-commit`. Changes there are picked up by the next run.

**Upgrade note.** A component whose System or Domain is declared in a file the cataloger reads re-keys from the bare name (`payments`) to the dotted path (`platform.payments`), and every declared Domain / System now gets its own `.domains` row. Update any policy or initiative that targets the old domain name. Scans with no `Domain` / `System` entities produce the same output as before.

### Restricting Synced Kinds

This cataloger only creates components from `kind: Component` entities. `Domain`, `System`, `API`, `Resource`, `User`, `Group`, `Location`, etc. are ignored for component creation. `Domain` and `System` entities feed the [Domain Hierarchy](#domain-hierarchy) instead.

### Files With Multiple Components

The common monorepo layout is one `catalog-info.yaml` per service directory, each declaring a single `Component` — one file, one component. A file that declares **zero** `Component` entities (e.g. only a `System` or `Domain`) or **more than one** `Component` is skipped, with a log line. This cataloger creates exactly one component per file and keys it to the file's directory, so it won't guess which of several `Component`s a multi-Component file maps to — give each `Component` its own directory's `catalog-info.yaml` to have it discovered. A skipped file's `Domain` / `System` entities still feed the [Domain Hierarchy](#domain-hierarchy).

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `discover` | **Scheduled.** Builds a scan set from `repos` plus any topic-matched repos discovered from `orgs`, walks each repo's tree via the Git Trees API, finds every `catalog-info.yaml`, fetches and parses each, and creates one component per file keyed to the file's directory. Writes owner / domain / tags plus `.domains` rows. Runs on a `cron` schedule. Requires `GH_TOKEN`. |
| `discover-on-commit` | **Commit-triggered.** The same scan as `discover`, run on every push to the default branch of the repository in `repos` instead of on a schedule. Fires only when `repos` names exactly one repository. Requires `GH_TOKEN`. |

## Hook Type

| Cataloger | Hook | Schedule / Trigger | Description |
|-----------|------|--------------------|-------------|
| `discover` | `cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per run (global), scanning every repo in the scan set (`repos` plus topic-matched repos from `orgs`) |
| `discover-on-commit` | `repo` | push to the default branch of the repo in `repos` | Runs once per push (global), scanning the same scan set |

Both hooks are global (once per run, no repo checkout), which is what lets this cataloger *create* components — per-component hooks (`component-cron`, `component-repo`) can only augment components that already exist. Daily at 03:00 is offset from the standard `0 2 * * *` so it lands after component-defining catalogers run. For updates on push, add `discover-on-commit` (see [Cataloging on commit](#cataloging-on-commit)).

## Installation

Add to your `lunar-config.yml` and list the repositories to scan:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    include: [discover]
    with:
      repos: "acme/monorepo,acme/platform"
```

Set the GitHub token used to walk each repo's tree and fetch each `catalog-info.yaml`:

```sh
lunar secret set GH_TOKEN <your-github-token> --scope cataloger
```

The token needs `Contents: Read` on every repo in `repos` (`repo` scope on a classic PAT; `contents: read` on a fine-grained PAT or GitHub App installation token). Many lunar-lib plugins reuse the same `GH_TOKEN`, so if you've already set it for `github-org` or the GitHub-API collectors, this cataloger picks it up automatically. All other inputs (`orgs`, `allowed_topics`, `disallowed_topics`, `include_archived`, `hierarchy_repos`, `hierarchy_paths`, `github_host`, `filenames`, `branch`, `exclude_paths`, `component_id_prefix`, `domain_annotation`, `tag_prefix`, `include_derived_tags`, `owner_format`, `default_owner`, `default_domain`, `allow_ignore_annotation`, `ignore_annotation`) are documented in `lunar-cataloger.yml`.

### Cataloging on commit

`discover` runs once a day, so a `catalog-info.yaml` added to a monorepo appears at the next 03:00 UTC run. Add `discover-on-commit` to run the same scan on every push to the monorepo's default branch:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    include: [discover, discover-on-commit]
    with:
      repos: "acme/monorepo"
```

- **One repository per import.** `discover-on-commit` fires only when `repos` names exactly one repository. To watch several monorepos, import the cataloger once per monorepo, each with its own `name` and `repos`.
- **Each push rescans the whole scan set**, so don't pair `discover-on-commit` with an ungated `orgs`. An import with no `include:` runs every variant, `discover-on-commit` included; pin `include: [discover]` to keep only the nightly scan.
- **The hub only acts on pushes to repositories it tracks**, so the monorepo needs a component before the first push counts, from `github-org` or a first `discover` run.
- **New and edited files take effect on push; removals (a deleted file, a dropped tag) wait for the nightly run.** Each variant keeps its own output, and the catalog merges the two.
- **A push that lands while a scan is running can be missed** if the scan already read the repo. The next push picks it up; otherwise it waits for the nightly run.

### GitHub Enterprise Server

Set `github_host` to read repositories from a GitHub Enterprise Server instance instead of github.com:

```yaml
catalogers:
  - name: monorepo-ghes
    uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    include: [discover, discover-on-commit]
    with:
      github_host: "github.acme.com"
      repos: "platform/monorepo"
```

```sh
lunar secret set GH_ENTERPRISE_TOKEN <your-ghes-token> --scope cataloger
```

- API calls go to `https://<github_host>/api/v3`, authenticated with `GH_ENTERPRISE_TOKEN`, or with `GH_TOKEN` when that isn't set.
- Component ids default to `<github_host>/<owner>/<repo>/<dir>`, matching the repo-level ids [`github-org`](../github-org) creates with the same `github_host`. An explicit `component_id_prefix` wins.
- One import reads one host. For repos on both github.com and GHES, import the cataloger once per host, each with its own `name`. `hierarchy_repos` must be on the import's host.
- `discover-on-commit` listens for pushes under both `<github_host>/<repo>` and `github.com/<repo>`, because the hub keys repo hooks by its own GitHub host (`HUB_GITHUB_HOST`). Give `github_host` as a bare hostname.

### Discovering repos by topic

Instead of hand-maintaining the `repos` list, you can auto-discover repositories across one or more organizations and opt them in by **GitHub topic**. Set `orgs` to the org(s) to scan and `allowed_topics` to the topic that marks a repo for monorepo cataloging:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    include: [discover]
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

- **`exclude_paths`** (platform-controlled) — a list of repo-relative paths/globs skipped before a component is ever created. It lives in `lunar-config.yml`, so dev teams can't override it. The default excludes the root `catalog-info.yaml`; add globs like `legacy/*/catalog-info.yaml` to fence off more. An excluded file's `Domain` / `System` entities are still read for the [Domain Hierarchy](#domain-hierarchy).
- **`lunar.io/ignore` annotation** (dev-delegated, gated) — set `allow_ignore_annotation: true` and any `Component` whose `catalog-info.yaml` carries `lunar.io/ignore: "true"` (key configurable via `ignore_annotation`) opts itself out. Left off by default, so opt-out stays platform-controlled unless you choose to delegate it.

### Targeting monorepos in a mixed fleet (monorepo + polyrepo)

An org often has **both** polyrepos (one service per repo, root `catalog-info.yaml` → the repo-level component) and monorepos (many services in subdirectories, and no root component wanted). The two strategies coexist without conflict: target the monorepos explicitly and let the normal repo-level flow handle everything else.

```yaml
catalogers:
  # Repo-level components for the whole org, EXCEPT the monorepos.
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
    include: [repos]
    with:
      org_name: "acme"
      exclude_repos: "big-monorepo"       # no repo-level component for the monorepo

  # Polyrepos: augment each root catalog-info onto its repo-level component.
  - uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    include:
      - augment            # Daily, via the GitHub Contents API
      - augment-on-commit  # On each commit, no token needed

  # Monorepos: one component per subdirectory catalog-info, root excluded by default.
  - uses: github://earthly/lunar-lib/catalogers/backstage-catalog-info-monorepo@v1.0.0
    include: [discover]
    with:
      repos: "acme/big-monorepo"
```

Each polyrepo gets a repo-level component from its root `catalog-info.yaml`; the monorepo gets one component per subdirectory and **no** root component. The flows don't overlap: `github-org` excludes the monorepo, and this cataloger is scoped to it by an explicit `repos` list rather than running across every repo. (The augment cataloger harmlessly no-ops on the monorepo's subcomponents — it looks for a root file at a path that isn't a real repo and skips on the 404.) This is the "target the monorepo directly" posture; because targeting is just the `repos` list plus `github-org`'s `exclude_repos`, a fleet can mix both strategies without a one-size-fits-all cataloger.

Instead of naming each monorepo, you can flip this to **topic-driven** targeting: give this cataloger `orgs` + `allowed_topics` (e.g. tag your monorepos `lunar-monorepo`) and let `github-org` skip the same set with a matching `disallowed_topics`. Onboarding a monorepo is then a GitHub topic, not a config edit on either cataloger. See [Discovering repos by topic](#discovering-repos-by-topic).

## Source System

[GitHub](https://github.com) or GitHub Enterprise Server (`github_host`) — when `orgs` is set the cataloger calls the [List organization repositories API](https://docs.github.com/en/rest/repos/repos#list-organization-repositories) (paged, 100/page) to enumerate candidate repos and filter them by topic; then, for every repo in the scan set and in `hierarchy_repos`, it calls the [Git Trees API](https://docs.github.com/en/rest/git/trees) once to enumerate files and the [Contents API](https://docs.github.com/en/rest/repos/contents) once per discovered `catalog-info.yaml` or `hierarchy_paths` match. Requirements:

- **`GH_TOKEN` secret** (or `GH_ENTERPRISE_TOKEN` for a GHES `github_host`) with `Contents: Read` on every repo in the scan set and in `hierarchy_repos`. When `orgs` is set, it must also be able to list the org's repositories (`read:org` / org membership for private repos, or `Metadata: Read` on a fine-grained PAT / App installation).
- **Component ids** are `<component_id_prefix><owner>/<repo>[/<dir>]`; the prefix defaults to `<github_host>/`.
- **A run that can't read anything fails.** If no repo in the scan set can be read, or a `hierarchy_repos` entry can't, the run exits non-zero instead of writing an empty catalog, so a hub on v4.4.0 or later keeps the last good one. A wrong `github_host` or token looks exactly like this. A single unreadable repo among readable ones is still just skipped.

### Scope and Roadmap

The cataloger targets the monorepo case that motivated it (a repo whose services each ship a `catalog-info.yaml`), scoped either by an explicit `repos` list or by org discovery with a GitHub-topic allow/blocklist (see [Discovering repos by topic](#discovering-repos-by-topic)).
