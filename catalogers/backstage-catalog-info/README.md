# Backstage catalog-info.yaml Cataloger

Augments existing Lunar components with metadata read from each repo's `catalog-info.yaml`, fetched directly via the GitHub Contents API.

## Overview

Augments existing Lunar components with owner, domain, tag, and meta metadata from each repo's `catalog-info.yaml`. Runs per component via the [`component-cron`](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) hook, fetches the file directly from the component's GitHub repo via the Contents API, picks the matching `Component` entity, and writes owner / domain / tags / meta to that component's catalog entry.

Because `component-cron` cannot create new components, pair this with a component-defining cataloger — typically [`github-org`](../github-org).

## Synced Data

This cataloger writes to the following Catalog JSON paths on each run:

| Path | Type | Description |
|------|------|-------------|
| `.components["$LUNAR_COMPONENT_ID"].owner` | string | `spec.owner` of the matched Backstage Component (or `default_owner` fallback) |
| `.components["$LUNAR_COMPONENT_ID"].domain` | string | `metadata.annotations[<domain_annotation>]` of the matched Component when `domain_annotation` is configured and the annotation is present; otherwise `spec.domain`, falling back to `spec.system`, then to the configured `default_domain` when none of those is set |
| `.components["$LUNAR_COMPONENT_ID"].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |
| `.components["$LUNAR_COMPONENT_ID"].meta` | object | Key/value meta sourced from annotations per the `meta_annotations` mapping. By default maps the `pagerduty.com/service-id` annotation onto `pagerduty/service-id`, which the [`pagerduty`](../../collectors/pagerduty) collector reads. Omitted entirely when no mapped annotation is present. |
| `.domains["<domain>"]` | object | Stub entry (`{}`) for each domain a component references. Hub catalog validation rejects components that reference unknown domains, so the cataloger writes the stub before the component entry. When the same `catalog-info.yaml` declares a matching `kind: Domain` or `kind: System` entity, its `metadata.description` and `spec.owner` are propagated into the stub. |

This cataloger does **not** define new components — that's out of scope for `component-cron`. Pair with a component-defining cataloger (see [Layering](#layering-with-a-component-defining-cataloger)). Domain entries are written as stubs only; for a richer global domain catalog, layer with the [`backstage`](../backstage) cataloger.

<details>
<summary>Example Catalog JSON output (across multiple component runs)</summary>

```json
{
  "components": {
    "github.com/acme/payment-api": {
      "owner": "group:default/team-payments",
      "domain": "platform.payments",
      "tags": ["bs-payments", "bs-tier1", "bs-type-service", "bs-lifecycle-production"],
      "meta": {"pagerduty/service-id": "PABC123"}
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
| `augment` | Fetches `catalog-info.yaml` from the current component's GitHub repo via the Contents API, parses the YAML (multi-document files supported), picks the matching `Component` entity, and writes its owner / domain / tags / meta to `.components["$LUNAR_COMPONENT_ID"]` in the Catalog JSON |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `component-cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per existing component |

`component-cron` invokes the cataloger separately for each Lunar component currently in the catalog, exposing the component identifier as `$LUNAR_COMPONENT_ID`. See the [cataloger-hooks reference](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) for the full contract.

Daily at 03:00 is a conservative default — `catalog-info.yaml` changes typically land on the order of hours-to-days, and the schedule is offset by an hour from the standard `0 2 * * *` so it lands after component-defining catalogers populate the catalog. Tighten the cadence by overriding `hook.schedule` in a fork.

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
```

Set the GitHub token used to fetch `catalog-info.yaml` from each repo:

```sh
lunar secret set GH_TOKEN <your-github-token>
```

The token needs `Contents: Read` on every repo this cataloger will read (`repo` scope on a classic PAT; `contents: read` on a fine-grained PAT or GitHub App installation token). Many lunar-lib plugins reuse the same `GH_TOKEN`, so if you've already set it for `github-org` or any of the GitHub-API collectors, this cataloger picks it up automatically.

Because `component-cron` only augments existing components, a component-defining cataloger must run first (see the [Layering](#layering-with-a-component-defining-cataloger) section below).

### Layering with a Component-Defining Cataloger

`component-cron` requires components to already exist. Run [`github-org`](../github-org) first so this cataloger has something to augment:

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

### Mapping Annotations to Component Meta (PagerDuty and others)

Several lunar-lib collectors resolve their per-component target from the Lunar component **meta** field rather than from config — for example, the [`pagerduty`](../../collectors/pagerduty) collector reads `pagerduty/service-id` from `LUNAR_COMPONENT_META` to know which PagerDuty service to query. That meta value has to come from somewhere; this cataloger sources it from a `catalog-info.yaml` annotation.

`meta_annotations` is a comma-separated list of `<annotation-key>=<meta-key>` pairs. For each pair, if the matched `Component` carries that annotation, its value is written to `.components["$LUNAR_COMPONENT_ID"].meta[<meta-key>]`. The default maps the annotation PagerDuty's [Backstage integration guide](https://support.pagerduty.com/main/docs/backstage-integration-guide) recommends:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    # default: meta_annotations: "pagerduty.com/service-id=pagerduty/service-id"
```

So a repo whose `catalog-info.yaml` has:

```yaml
metadata:
  annotations:
    pagerduty.com/service-id: PABC123
```

gets `meta: {"pagerduty/service-id": "PABC123"}`, and the `pagerduty` collector (and the `oncall` guardrails behind it) works with no further per-component config. Note the annotation namespace is `pagerduty.com/` (the Backstage/PagerDuty convention) while the Lunar meta key is `pagerduty/service-id` — the mapping bridges the two.

Add pairs to feed other collectors:

```yaml
    with:
      meta_annotations: "pagerduty.com/service-id=pagerduty/service-id,sonarqube.io/project-key=sonarqube/project-key"
```

Whitespace around each pair and its `=` is trimmed. Set `meta_annotations` to empty to write no meta at all. A pair whose annotation is absent on a given component is skipped, and `.meta` is omitted entirely when nothing matches (so it never clobbers meta set elsewhere with an empty object).

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. `default_owner` is also written verbatim, regardless of `owner_format`.

## Source System

[GitHub](https://github.com) — the cataloger calls the [Contents API](https://docs.github.com/en/rest/repos/contents) once per component invocation to fetch `catalog-info.yaml` from each repo. Requirements:

- **`GH_TOKEN` secret** with read access to every repo this cataloger will read (`Contents: Read` on a fine-grained PAT, `repo` on a classic PAT, or `contents: read` on a GitHub App installation token).
- **Component IDs match `<component_id_prefix><owner>/<repo>`** (default `github.com/<owner>/<repo>`). Non-GitHub component IDs are skipped silently — this cataloger is GitHub-specific.

The cataloger makes no other external calls. YAML parsing and entity selection happen in-process; the only outbound traffic is the GitHub fetch.
