# Backstage catalog-info.yaml Cataloger

Walks GitHub repos and writes Backstage component/domain metadata pulled from each repo's `catalog-info.yaml` into Lunar.

## Overview

This cataloger reads Backstage `catalog-info.yaml` files directly from source repos — no running Backstage server required. For each repo in a configured GitHub organisation it fetches `catalog-info.yaml`, parses every Backstage entity document, and writes Component / Domain entries into the Lunar catalog. Use this when your Backstage source-of-truth lives in repo files.

It complements [`backstage`](../backstage), which reads from a live Backstage server's REST API — the two are layerable. It also complements the per-repo [`backstage` collector](../../collectors/backstage), which writes `.catalog.native.backstage` for each individual repo during local / CI Lunar runs.

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | `spec.owner` of the Backstage Component (or `default_owner` fallback) |
| `.components[*].domain` | string | `spec.domain` of the Backstage Component (falls back to `spec.system` when `domain` is absent) |
| `.components[*].tags[]` | array | `metadata.tags` plus derived `type-*` / `lifecycle-*` tags, all with `tag_prefix` |
| `.domains[*].description` | string | `metadata.description` of the Backstage Domain |
| `.domains[*].owner` | string | `spec.owner` of the Backstage Domain |

<details>
<summary>Example Catalog JSON output</summary>

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
      "description": "Payment processing and billing",
      "owner": "group:default/platform-leads"
    },
    "platform.frontend": {
      "description": "Customer-facing web surfaces",
      "owner": "group:default/platform-leads"
    }
  }
}
```

</details>

## Catalogers

| Cataloger | Description |
|-----------|-------------|
| `sync` | Enumerates repos in the configured GitHub org, fetches each repo's `catalog-info.yaml`, parses every Backstage entity document, and writes Components / Domains (and optionally Systems, APIs, Resources) to the Lunar catalog |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `cron` | `0 2 * * *` | Runs daily at 02:00 UTC |

Daily is the conservative default. A full sweep enumerates every repo in the org and fetches one or more YAML files per repo via the GitHub contents API — at thousands of repos this is non-trivial work for both the GitHub API and the Lunar Runner. Ownership / domain / tag values in `catalog-info.yaml` also change on the order of hours-to-days (PRs landing, team handovers), so a nightly cycle covers the data velocity for almost every org. Smaller orgs can tighten the cadence by overriding `hook.schedule` in a fork.

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    with:
      org_name: "acme"
```

Configure the GitHub token as a Lunar secret:

```bash
lunar secret set GITHUB_TOKEN <your-token>
```

The cataloger reads `LUNAR_SECRET_GITHUB_TOKEN` automatically.

### Layering with the GitHub Org Cataloger

`github-org` discovers repos and writes baseline metadata (visibility, topics, archived state); `backstage-catalog-info` layers domain / owner / tags on top from each repo's `catalog-info.yaml`. Declare `github-org` first so its values are present when `backstage-catalog-info` runs:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    with:
      org_name: "acme"
```

Per Lunar's [merge precedence](../../ai-context/cataloger-reference.md#merge-precedence), catalogers declared later override earlier ones.

### Layering with the Live Backstage Cataloger

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage-catalog-info@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
```

Repo-file metadata first, server-resolved metadata second — useful when the Backstage server adds processed annotations (e.g. ownership resolved from group hierarchies) that the raw files don't carry.

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

### Mapping Components to Repos

Components are keyed by `component_id_prefix + <annotation value>` when the configured `component_id_annotation` is present on the entity, or `component_id_prefix + <owner>/<repo>` (derived from the GitHub repo the file came from) when it isn't. Defaults assume the standard `github.com/project-slug`:

```yaml
with:
  component_id_annotation: "github.com/project-slug"  # value: "acme/payment-api"
  component_id_prefix: "github.com/"                    # → "github.com/acme/payment-api"
```

The fallback to `<owner>/<repo>` means a repo with a `catalog-info.yaml` that omits the annotation still gets a sensible Lunar component ID — no manual annotation gardening required to onboard.

### Filtering Repos

`include_repos` / `exclude_repos` accept comma-separated glob patterns matched against the repo name (not the `<owner>/<repo>`). `include_archived`, `include_public`, `include_private`, `include_internal` toggle the visibility-class filters. All four behave the same way as in the [`github-org`](../github-org) cataloger.

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. `default_owner` is also written verbatim, regardless of `owner_format`.

## Source System

This cataloger reads from GitHub. It requires:

1. **A GitHub token** (`LUNAR_SECRET_GITHUB_TOKEN`) with `repo` scope for private/internal repos and `read:org` to enumerate the org's repository list. Public-only scans still need a token to clear the unauthenticated rate limit.
2. **Read access** to the files listed in `paths` (default `catalog-info.yaml,catalog-info.yml`) at the configured `branch` — the repo's default branch when `branch` is empty.

Backstage parses YAML inputs against its own entity schema, but this cataloger does not invoke the Backstage validator — invalid entities are skipped silently with a log line. Use the per-repo [`backstage` collector](../../collectors/backstage) (which **does** invoke validation) when authoritative lint findings are required.
