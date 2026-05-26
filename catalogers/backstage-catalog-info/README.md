# Backstage catalog-info.yaml Cataloger

Augments existing Lunar components with metadata read from each repo's `catalog-info.yaml`.

## Overview

Augments existing Lunar components with owner, domain, and tag metadata from each repo's `catalog-info.yaml`. Runs per component via the [`component-cron`](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) hook, reading the Backstage entity that the per-repo [`backstage` collector](../../collectors/backstage) has already written to `.catalog.native.backstage`, then writing owner / domain / tags to that component's catalog entry.

Makes no GitHub API calls and needs no auth — it transforms already-collected data. Because `component-cron` cannot create new components, pair it with a component-defining cataloger — typically [`github-org`](../github-org), or the live-API [`backstage`](../backstage) cataloger.

## Synced Data

This cataloger writes to the following Catalog JSON paths (on the **current** component only):

| Path | Type | Description |
|------|------|-------------|
| `.components["$LUNAR_COMPONENT_ID"].owner` | string | `spec.owner` of the matched Backstage Component (or `default_owner` fallback) |
| `.components["$LUNAR_COMPONENT_ID"].domain` | string | `spec.domain` of the matched Component (falls back to `spec.system` when `domain` is absent) |
| `.components["$LUNAR_COMPONENT_ID"].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |

This cataloger does **not** define new components and does **not** write to `.domains`. Both are out of scope for `component-cron` — use a global cataloger for those.

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
  }
}
```

</details>

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `augment` | Reads the Backstage entity at `.catalog.native.backstage` from the current component's Component JSON, verifies it corresponds to this component, and writes its owner / domain / tags to `.components["$LUNAR_COMPONENT_ID"]` in the Catalog JSON |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `component-cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per existing component |

`component-cron` invokes the cataloger separately for each Lunar component currently in the catalog, exposing the component identifier as `$LUNAR_COMPONENT_ID`. No repository clone — the cataloger reads from the component's already-collected data. See the [cataloger-hooks reference](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) for the full contract.

Daily at 03:00 is a conservative default — `catalog-info.yaml` changes typically land on the order of hours-to-days (PRs adding new components, team handovers), and the schedule is offset by an hour from the standard `0 2 * * *` to let component-defining catalogers and the per-repo `backstage` collector's output land first. Tighten the cadence by overriding `hook.schedule` in a fork.

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
```

Because `component-cron` only augments existing components, a component-defining cataloger must run first (see the [Layering](#layering-with-a-component-defining-cataloger) section below). Each component's repo must also have the per-repo [`backstage` collector](../../collectors/backstage) installed so that `.catalog.native.backstage` is populated on the component — components missing this data are skipped silently.

No secrets to configure. The cataloger reads pre-collected data and makes no external API calls.

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
| You can install the per-repo [`backstage` collector](../../collectors/backstage) on each component repo (it parses `catalog-info.yaml` automatically) | You want a single global pull at fixed cadence with no per-repo collector dependency |

Running both would write to the same `.components` keys with the same data via different paths — wasteful and the last-declared cataloger silently wins. Don't layer them; pick the one that matches your Backstage setup.

### Mapping Components to Backstage Entities

The cataloger needs to confirm that the `Component` entity in `.catalog.native.backstage` corresponds to the current Lunar component before writing back. Matching is two-step:

1. **Annotation match (preferred).** Look for `metadata.annotations[<component_id_annotation>]` and confirm its value, prefixed with `component_id_prefix`, equals `$LUNAR_COMPONENT_ID`. Defaults assume the standard `github.com/project-slug` annotation:

   ```yaml
   with:
     component_id_annotation: "github.com/project-slug"  # value: "acme/payment-api"
     component_id_prefix: "github.com/"                    # → "github.com/acme/payment-api"
   ```

2. **ID fallback.** If no annotation is set on the entity, fall back to checking that `$LUNAR_COMPONENT_ID` itself starts with `component_id_prefix`. This covers the common case of a `catalog-info.yaml` with a single Component entity and no explicit project-slug annotation, where the component ID already follows the `github.com/owner/repo` convention.

Entities whose `.catalog.native.backstage` is not a Backstage `Component`, or whose annotation doesn't match the current component, are skipped silently — no error, no partial write. This guards against the rare case of `.catalog.native.backstage` being stale or belonging to a different component.

### Restricting Synced Kinds

This cataloger only processes `kind: Component` entities. `Domain`, `System`, `API`, `Resource`, `User`, `Group`, `Location`, etc. are ignored — they're either container-level concepts (handled by a global cataloger like [`backstage`](../backstage)) or not Lunar catalog concerns.

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. `default_owner` is also written verbatim, regardless of `owner_format`.

## Source System

This cataloger has no direct source system — it reads pre-collected data and makes no external API calls. The data flow is two-stage:

1. **Per-repo, by the [`backstage` collector](../../collectors/backstage):** parses `catalog-info.yaml` from the repo and writes the parsed entity to `.catalog.native.backstage` on the component (with `valid` / `errors[]` flags from its lint pass).
2. **Per-component, on this cataloger's schedule:** reads `.catalog.native.backstage` from the component and projects owner / domain / tags into `.components[$LUNAR_COMPONENT_ID]` in the Catalog JSON.

The collector handles validation and path discovery once; this cataloger trusts its output. If a component has no `.catalog.native.backstage` (collector not configured, repo has no `catalog-info.yaml`, or CI hasn't run yet), the component is skipped silently. The cataloger does **not** read invalid entities (`.catalog.native.backstage.valid == false`) — the collector's lint findings are authoritative.
