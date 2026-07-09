# Backstage catalog-info.yaml Cataloger

Augments existing Lunar components with metadata read from each repo's `catalog-info.yaml`, fetched directly via the GitHub Contents API.

## Overview

Augments existing Lunar components with owner, domain, and tag metadata read from each repo's `catalog-info.yaml` — it picks the matching `Component` entity and writes owner / domain / tags to that component's catalog entry. The same augmentation runs in two trigger variants: `augment` refreshes the catalog on a daily schedule (fetching the file via the GitHub Contents API), while `augment-on-commit` updates a component the moment its repo is committed to (reading the file from the checkout, no token). Both only enrich components that already exist, so pair this with a component-defining cataloger such as [`github-org`](../github-org).

## Synced Data

This cataloger writes to the following Catalog JSON paths on each run:

| Path | Type | Description |
|------|------|-------------|
| `.components["$LUNAR_COMPONENT_ID"].owner` | string | `spec.owner` of the matched Backstage Component (or `default_owner` fallback) |
| `.components["$LUNAR_COMPONENT_ID"].domain` | string | `metadata.annotations[<domain_annotation>]` of the matched Component when `domain_annotation` is configured and the annotation is present; otherwise `spec.domain`, falling back to `spec.system`, then to the configured `default_domain` when none of those is set |
| `.components["$LUNAR_COMPONENT_ID"].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |
| `.domains["<domain>"]` | object | Stub entry (`{}`) for each domain a component references. Hub catalog validation rejects components that reference unknown domains, so the cataloger writes the stub before the component entry. When the same `catalog-info.yaml` declares a matching `kind: Domain` or `kind: System` entity, its `metadata.description` and `spec.owner` are propagated into the stub. |

This cataloger does **not** define new components — both the `component-cron` and `component-repo` hooks augment existing components only. Pair with a component-defining cataloger (see [Layering](#layering-with-a-component-defining-cataloger)). Domain entries are written as stubs only; for a richer global domain catalog, layer with the [`backstage`](../backstage) cataloger.

<details>
<summary>Example Catalog JSON output (across multiple component runs)</summary>

```json
{
  "components": {
    "github.com/acme/payment-api": {
      "owner": "group:default/team-payments",
      "domain": "platform.payments",
      "tags": ["bs-payments", "bs-tier1", "bs-type-service", "bs-lifecycle-production"]
    },
    "github.com/acme/web-app": {
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

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `augment` | **Scheduled.** Fetches `catalog-info.yaml` from the current component's GitHub repo via the Contents API, parses the YAML (multi-document files supported), picks the matching `Component` entity, and writes its owner / domain / tags to `.components["$LUNAR_COMPONENT_ID"]` in the Catalog JSON. Runs on a `component-cron` schedule. Requires `GH_TOKEN`. |
| `augment-on-commit` | **Commit-triggered.** Same parsing, matching, and output as `augment`, but runs on the `component-repo` hook — it fires when the component's repo receives a commit and reads `catalog-info.yaml` from the checkout instead of the Contents API. No `GH_TOKEN` required. Use it for near-real-time updates; see [Choosing a variant](#choosing-a-variant). |

## Hook Type

| Cataloger | Hook | Schedule / Trigger | Description |
|-----------|------|--------------------|-------------|
| `augment` | `component-cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per existing component |
| `augment-on-commit` | `component-repo` | on commit to a component's repo | Runs whenever a component's repo receives a commit, once per affected component |

Both hooks invoke the cataloger separately for each Lunar component, exposing the component identifier as `$LUNAR_COMPONENT_ID`. The difference is *when* and *with what*: `component-cron` fires on a schedule with no repo checkout (so `augment` fetches the file over the API), while `component-repo` fires on a commit with the component's repo checked out (so `augment-on-commit` reads the file locally). See the cataloger-hooks reference for the full contract on [`component-cron`](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) and [`component-repo`](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-repo).

Daily at 03:00 is a conservative default for `augment` — it's offset by an hour from the standard `0 2 * * *` so it lands after component-defining catalogers populate the catalog. Tighten the cadence by overriding `hook.schedule` in a fork.

### Choosing a variant

The two sub-catalogers produce identical catalog entries from the same `catalog-info.yaml`; pick by how fresh you need the data and whether a checkout is available:

| | `augment` (`component-cron`) | `augment-on-commit` (`component-repo`) |
|--|------------------------------|----------------------------------------|
| **Freshness** | Up to a day stale (next cron) | Near-real-time — updates on the triggering commit |
| **GitHub token** | Required (`GH_TOKEN`, Contents API) | Not required (reads the checkout) |
| **Catches drift independent of commits** | Yes — re-reads every component each cron | No — only fires when a repo is committed to |
| **Covers components whose repo is quiet** | Yes | No, until the next commit |

They aren't mutually exclusive. Running **both** is a reasonable default: `augment-on-commit` keeps active repos current within seconds of a change, while the nightly `augment` backfills components that haven't seen a commit and re-asserts state. Selecting a subset is done with `include` / `exclude` (see [Installation](#installation)). When both run, they write the same keys with the same data, so there's no conflict — the later writer simply re-asserts the value.

## Installation

Add to your `lunar-config.yml`. With no `include` / `exclude`, both sub-catalogers run:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
```

Pick a single variant with `include` (see [Choosing a variant](#choosing-a-variant)):

```yaml
catalogers:
  # Commit-triggered only — near-real-time, no GitHub token needed
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    include: [augment-on-commit]
```

```yaml
catalogers:
  # Scheduled only — daily backfill via the GitHub Contents API
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    include: [augment]
```

If you run the `augment` variant (scheduled / Contents API), set the GitHub token used to fetch `catalog-info.yaml` from each repo:

```sh
lunar secret set GH_TOKEN <your-github-token>
```

The token needs `Contents: Read` on every repo this cataloger will read (`repo` scope on a classic PAT; `contents: read` on a fine-grained PAT or GitHub App installation token). Many lunar-lib plugins reuse the same `GH_TOKEN`, so if you've already set it for `github-org` or any of the GitHub-API collectors, this cataloger picks it up automatically. The `augment-on-commit` variant reads the file from the `component-repo` checkout, so it needs no token — if you run only that variant you can skip this step.

Because both variants only augment existing components, a component-defining cataloger must run first (see the [Layering](#layering-with-a-component-defining-cataloger) section below).

### Layering with a Component-Defining Cataloger

Both variants augment existing components only — neither `component-cron` nor `component-repo` can create them. Run [`github-org`](../github-org) first so this cataloger has something to augment:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
```

### Pick This or the Live Backstage Cataloger — Not Both

The data source is the same Backstage metadata; the difference is where you read it from. Pick one based on whether you run a Backstage server:

| Use this cataloger (`backstage-catalog-info`) when… | Use the live-API [`backstage`](../backstage) cataloger when… |
|------------------------------------------------------|--------------------------------------------------------------|
| You don't run a Backstage server — `catalog-info.yaml` files in repos are the source of truth | You run a Backstage instance and want its server-side processing (group hierarchy resolution, namespace defaults, relations) |
| You want repo-file fidelity (whatever is committed is what shows up) | You want a single global pull at fixed cadence against a central API |

Running both would write to the same `.components` keys with the same data via different paths — wasteful and the last-declared cataloger silently wins. Don't layer them; pick the one that matches your Backstage setup.

### Mapping Components to Backstage Entities

A `catalog-info.yaml` may declare more than one entity (monorepos commonly ship a `Component` + a `System` in one file, or several `Component`s for sub-packages). The cataloger picks which `Component` corresponds to the current Lunar component using two rules:

1. **Annotation match (preferred).** If any `Component` entity in the file has the configured annotation, only annotated entries participate in matching: the cataloger picks the one whose `metadata.annotations[<component_id_annotation>]` value, prefixed with `component_id_prefix`, equals `$LUNAR_COMPONENT_ID`. Defaults assume the standard `github.com/project-slug` annotation:

   ```yaml
   with:
     component_id_annotation: "github.com/project-slug"  # value: "acme/payment-api"
     component_id_prefix: "github.com/"                    # → "github.com/acme/payment-api"
   ```

   If no annotated entry matches, the cataloger skips silently — it refuses to guess for a repo that already uses annotations to disambiguate.

2. **Single-Component fallback.** If no `Component` entity has the annotation and the file contains exactly one `Component`, that entity is used. This covers the common single-Component-per-repo case where the annotation isn't worth maintaining.

If the file has multiple `Component` entities and none are annotated, the cataloger skips silently — the YAML needs annotations to disambiguate.

### Restricting Synced Kinds

This cataloger only processes `kind: Component` entities. `Domain`, `System`, `API`, `Resource`, `User`, `Group`, `Location`, etc. are ignored — they're either container-level concepts (handled by a global cataloger like [`backstage`](../backstage)) or not Lunar catalog concerns.

### Excluding Components from Augmentation

Two inputs decide which components this cataloger skips, giving platform teams a choice between keeping control and delegating opt-out to dev teams:

- **`ignore_components` (platform-controlled).** A comma-separated list of component ids to skip — matched by exact id or glob (e.g. `github.com/acme/legacy-*`). A matched component is skipped before its `catalog-info.yaml` is even fetched. Because the list lives in `lunar-config.yml`, dev teams can't override it — this is the "platform team keeps control" path.

  ```yaml
  with:
    ignore_components: "github.com/acme/sandbox,github.com/acme/legacy-*"
  ```

- **`lunar.io/ignore` annotation (dev-delegated, gated).** When `allow_ignore_annotation: true`, any component whose matched `Component` carries `lunar.io/ignore: "true"` (values `true` / `yes` / `1`; key configurable via `ignore_annotation`) opts itself out of augmentation. This is the "platform team delegates opt-out to dev teams" path. It's **off by default** — until you enable the gate, the annotation is ignored and exclusion stays entirely platform-controlled.

  ```yaml
  with:
    allow_ignore_annotation: true   # let repos self-exclude via lunar.io/ignore
  ```

The two compose: `ignore_components` is always enforced; the annotation only when its gate is on. Use the list alone for hard central control, the gate alone (or both) to let dev teams remove their own components.

### Sourcing the Domain from a Custom Annotation

Some orgs model component domains via a custom annotation rather than the canonical Backstage `spec.domain` field — for example, to express a hierarchical name like `engineering.tooling.observability` that Backstage's flat `spec.domain` doesn't model well. Set `domain_annotation` to that key and the cataloger reads it from `metadata.annotations[<key>]`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    with:
      domain_annotation: "yourorg.example.com/domain"
```

When set and the matched Component has that annotation, its value wins over `spec.domain` / `spec.system`. When the annotation is absent on a given entity, the cataloger falls back to `spec.domain` then `spec.system` as usual. Leave `domain_annotation` empty (the default) to use only the canonical Backstage fields.

### Default Domain

Not every `catalog-info.yaml` sets a domain. When a matched Component resolves to no domain at all — no `domain_annotation` value, no `spec.domain`, and no `spec.system` — the cataloger leaves the component's `domain` unset by default. Set `default_domain` to assign a fallback instead:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    with:
      default_domain: "engineering"
```

The value is written verbatim, and a stub `.domains["<default_domain>"]` entry is written alongside it so the hub's domain validation accepts the reference (the same stub-write the cataloger does for any other domain). `default_domain` is purely a last-resort fallback — it never overrides a domain that the file already provides through any of the sources above. Leave it empty (the default) to keep domain-less components unset.

This mirrors `default_owner` for ownership: use it to funnel otherwise-uncategorized repos into a sensible default domain rather than leaving them blank.

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. `default_owner` is also written verbatim, regardless of `owner_format`.

## Source System

[GitHub](https://github.com) — the cataloger calls the [Contents API](https://docs.github.com/en/rest/repos/contents) once per component invocation to fetch `catalog-info.yaml` from each repo. Requirements:

- **`GH_TOKEN` secret** with read access to every repo this cataloger will read (`Contents: Read` on a fine-grained PAT, `repo` on a classic PAT, or `contents: read` on a GitHub App installation token).
- **Component IDs match `<component_id_prefix><owner>/<repo>`** (default `github.com/<owner>/<repo>`). Non-GitHub component IDs are skipped silently — this cataloger is GitHub-specific.

The cataloger makes no other external calls. YAML parsing and entity selection happen in-process; the only outbound traffic is the GitHub fetch.
