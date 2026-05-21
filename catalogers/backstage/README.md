# Backstage Cataloger

Syncs components and domains from a Backstage software catalog into Lunar.

## Overview

This cataloger reads entities from a [Backstage](https://backstage.io) instance via its REST API (`/api/catalog/entities`) and writes them into the Lunar catalog. Component entities become Lunar components (with owner, domain, and tags); Domain entities become Lunar domains (with description and owner). It complements the [`backstage` collector](../../collectors/backstage), which parses per-repo `catalog-info.yaml` files — this cataloger reads the rolled-up view from the Backstage server itself.

Use this cataloger when you run a Backstage instance and want Lunar to inherit ownership, domain, and tag metadata from it without restating the catalog inside `lunar-config.yml`.

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | `spec.owner` of the Backstage Component (or `default_owner` fallback) |
| `.components[*].domain` | string | `spec.domain` of the Backstage Component |
| `.components[*].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |
| `.domains[*].description` | string | `metadata.description` of the Backstage Domain |
| `.domains[*].owner` | string | `spec.owner` of the Backstage Domain |

<details>
<summary>Example Catalog JSON output</summary>

```json
{
  "components": {
    "github.com/acme/payment-api": {
      "owner": "team-payments@acme.com",
      "domain": "platform.payments",
      "tags": ["bs-payments", "bs-tier1", "bs-type-service", "bs-lifecycle-production"]
    },
    "github.com/acme/web-app": {
      "owner": "team-web@acme.com",
      "domain": "platform.frontend",
      "tags": ["bs-frontend", "bs-type-website", "bs-lifecycle-production"]
    }
  },
  "domains": {
    "platform.payments": {
      "description": "Payment processing and billing",
      "owner": "platform-leads@acme.com"
    },
    "platform.frontend": {
      "description": "Customer-facing web surfaces",
      "owner": "platform-leads@acme.com"
    }
  }
}
```

</details>

## Catalogers

This integration provides the following catalogers:

| Cataloger | Description |
|-----------|-------------|
| `sync` | Fetches entities from the Backstage catalog API and writes Components, Domains (and optionally Systems, APIs, Resources) to the Lunar catalog |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `cron` | `0 2 * * *` | Runs daily at 2am UTC |

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
```

### Authenticated Backstage

Most internal Backstage deployments require a bearer token. Configure it as a Lunar secret:

```bash
lunar secret set BACKSTAGE_TOKEN <your-token>
```

The cataloger reads `LUNAR_SECRET_BACKSTAGE_TOKEN` automatically — no extra `with:` is needed.

### Layering with the GitHub Org Cataloger

For organisations that already run [`github-org`](../github-org) to enumerate repos, run Backstage *after* it so its owner/domain/tag values override the GitHub defaults:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github://earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
```

Per Lunar's [merge precedence](../../ai-context/cataloger-reference.md#merge-precedence), catalogers declared later override earlier ones.

### Mapping Components to Repos

Backstage components are matched to Lunar components by reading an annotation on each Backstage Component entity. Defaults assume the standard `github.com/project-slug` annotation:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
      component_id_annotation: "github.com/project-slug"  # value: "acme/payment-api"
      component_id_prefix: "github.com/"                    # → "github.com/acme/payment-api"
```

For GitLab or other forges, point at the appropriate annotation:

```yaml
with:
  component_id_annotation: "gitlab.com/project-slug"
  component_id_prefix: "gitlab.com/"
```

### Restricting Synced Kinds

By default, `Component` and `Domain` entities are synced. Include other kinds explicitly:

```yaml
with:
  entity_kinds: "Component,Domain,System,API"
```

| Backstage kind | Synced to |
|----------------|-----------|
| `Component`, `API`, `Resource` | `.components` |
| `Domain`, `System` | `.domains` |
| Other kinds (`User`, `Group`, `Location`, …) | Ignored |

### Filtering Entities

Pass a raw [Backstage filter expression](https://backstage.io/docs/features/software-catalog/software-catalog-api/#get-entities) through `filter`:

```yaml
with:
  filter: "metadata.annotations.team=platform"
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `backstage_url` | Yes | — | Base URL of the Backstage instance |
| `entity_kinds` | No | `Component,Domain` | Comma-separated kinds to sync |
| `namespace` | No | `default` | Backstage namespace (`*` for all) |
| `component_id_annotation` | No | `github.com/project-slug` | Annotation holding the repo slug |
| `component_id_prefix` | No | `github.com/` | Prefix prepended to the annotation value |
| `tag_prefix` | No | `bs-` | Prefix added to all emitted tags |
| `include_derived_tags` | No | `true` | Emit `type-*` and `lifecycle-*` tags |
| `default_owner` | No | _empty_ | Fallback owner for entities without `spec.owner` |
| `domain_default_description` | No | _empty_ | Fallback description for domains |
| `filter` | No | _empty_ | Extra raw Backstage filter |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `BACKSTAGE_TOKEN` | No | Bearer token for the Backstage API. Most internal deployments require this. |

## Source System

This cataloger calls the [Backstage Catalog REST API](https://backstage.io/docs/features/software-catalog/software-catalog-api/) — specifically the `/api/catalog/entities` endpoint. It requires:

1. **Network reach** from the Lunar Runner to the Backstage instance
2. **A bearer token** (`LUNAR_SECRET_BACKSTAGE_TOKEN`) if the instance enforces authentication
3. **Read access** to the kinds configured in `entity_kinds`

Pagination is handled automatically; the cataloger streams pages until all matching entities are fetched.
