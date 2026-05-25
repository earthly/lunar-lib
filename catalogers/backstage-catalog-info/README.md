# Backstage catalog-info.yaml Cataloger

Augments existing Lunar components with metadata read from each repo's `catalog-info.yaml`.

## Overview

Augments existing Lunar components with owner, domain, and tag metadata pulled from each repo's `catalog-info.yaml`. Runs per component via the [`component-cron`](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) hook — matches the current Lunar component against entries in the YAML and writes back to that component's catalog entry only.

Because `component-cron` cannot create new components, pair this with one that does — typically [`github-org`](../github-org) for org-wide discovery, or the live-API [`backstage`](../backstage) cataloger. Complements the per-repo [`backstage` collector](../../collectors/backstage), which writes `.catalog.native.backstage` during CI Lunar runs.

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
| `augment` | Reads `catalog-info.yaml` from the current component's repo, finds the matching Backstage Component entity, and writes its owner / domain / tags back to `.components["$LUNAR_COMPONENT_ID"]` |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `component-cron` | `0 3 * * *` | Runs daily at 03:00 UTC, once per existing component |

`component-cron` means the cataloger is invoked separately for each Lunar component currently in the catalog, with the component identifier exposed as `$LUNAR_COMPONENT_ID` and no repository clone (the script reads the component's existing data via `lunar component get-json`). See the [cataloger-hooks reference](https://docs-lunar.earthly.dev/configuration/lunar-config/cataloger-hooks#component-cron) for the full contract.

Daily at 03:00 is a conservative default — `catalog-info.yaml` changes typically land on the order of hours-to-days (PRs adding new components, team handovers), and the schedule is offset by an hour from the standard `0 2 * * *` to let component-defining catalogers run first. Tighten the cadence by overriding `hook.schedule` in a fork.

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
```

Because `component-cron` only augments existing components, a component-defining cataloger must run first (see the [Layering](#layering-with-a-component-defining-cataloger) section below).

Configure the GitHub token as a Lunar secret:

```bash
lunar secret set GITHUB_TOKEN <your-token>
```

The cataloger reads `LUNAR_SECRET_GITHUB_TOKEN` automatically.

### Layering with a Component-Defining Cataloger

`component-cron` requires components to already exist. Run [`github-org`](../github-org) first so this cataloger has something to augment:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
```

### Layering with the Live Backstage Cataloger

The live-API [`backstage`](../backstage) cataloger also writes to `.components` (via a global `cron` hook). Layering both is fine — declare whichever should win **last**:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0

  - uses: github.com/earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
```

Per Lunar's [merge precedence](../../ai-context/cataloger-reference.md#merge-precedence), the last cataloger wins — so the live server's processed annotations (e.g. ownership resolved from group hierarchies) override the raw file values.

### Mapping Components to Backstage Entities

The cataloger needs to find which Backstage `Component` entity in the YAML corresponds to the current Lunar component. Matching is two-step:

1. **Annotation match (preferred).** Look for the entity whose `metadata.annotations[<component_id_annotation>]` value, prefixed with `component_id_prefix`, equals `$LUNAR_COMPONENT_ID`. Defaults assume the standard `github.com/project-slug` annotation:

   ```yaml
   with:
     component_id_annotation: "github.com/project-slug"  # value: "acme/payment-api"
     component_id_prefix: "github.com/"                    # → "github.com/acme/payment-api"
   ```

2. **Repo fallback.** If no entity carries the annotation, fall back to matching `component_id_prefix + <owner>/<repo>` (derived from the GitHub repo the file came from) against `$LUNAR_COMPONENT_ID`. This means a `catalog-info.yaml` with a single Component entity and no annotation still gets matched correctly when the component ID follows the `github.com/owner/repo` convention.

Components without a matching entity in their `catalog-info.yaml` are skipped silently — no error, no partial write.

### Restricting Synced Kinds

This cataloger only processes `kind: Component` entities. `Domain`, `System`, `API`, `Resource`, `User`, `Group`, `Location`, etc. are ignored — they're either container-level concepts (handled by a global cataloger like [`backstage`](../backstage)) or not Lunar catalog concerns.

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. `default_owner` is also written verbatim, regardless of `owner_format`.

## Source System

This cataloger reads from GitHub. It requires:

1. **A GitHub token** (`LUNAR_SECRET_GITHUB_TOKEN`) with read access to the component repos. Public-only setups still need a token to clear the unauthenticated rate limit.
2. **Read access** to the files listed in `paths` (default `catalog-info.yaml,catalog-info.yml`) at the configured `branch` — the repo's default branch when `branch` is empty.

Backstage parses YAML inputs against its own entity schema, but this cataloger does not invoke the Backstage validator — invalid entities are skipped silently with a log line. Use the per-repo [`backstage` collector](../../collectors/backstage) (which **does** invoke validation) when authoritative lint findings are required.
