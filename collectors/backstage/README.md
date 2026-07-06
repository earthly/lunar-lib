# Backstage Collector

Parses and lints Backstage `catalog-info.yaml` files.

## Overview

This collector scans the repository for a Backstage catalog definition file (`catalog-info.yaml` or `catalog-info.yml`), parses it, and lints it for schema/syntax issues. The raw Backstage descriptor (apiVersion, kind, metadata, spec) is written to the `.catalog.native.backstage` Component JSON path as-is — annotations keep their original `backstage.io/` or vendor prefixes. The search paths are configurable via the `paths` input.

Optionally, when a `backstage_url` is configured, it also cross-checks the domain and system referenced in `catalog-info.yaml` against the live Backstage catalog and records whether those entities exist under `.catalog.native.backstage.refs`.

## Collected Data

When a catalog-info file is found, this collector writes to the following Component JSON paths. When no file is found, the `.catalog.native.backstage` namespace is **not written** — absence of the namespace is the signal.

| Path | Type | Description |
|------|------|-------------|
| `.catalog.native.backstage.valid` | boolean | Whether the catalog-info file passed lint/schema checks |
| `.catalog.native.backstage.errors[]` | array | Lint findings (each with `line`, `message`, `severity`) |
| `.catalog.native.backstage.path` | string | Relative path to the file that was parsed |
| `.catalog.native.backstage.apiVersion` | string | Backstage API version (e.g. `backstage.io/v1alpha1`) |
| `.catalog.native.backstage.kind` | string | Entity kind (e.g. `Component`, `System`, `API`) |
| `.catalog.native.backstage.metadata` | object | Raw `metadata` block (`name`, `description`, `annotations`, `tags`, etc.) |
| `.catalog.native.backstage.spec` | object | Raw `spec` block (`type`, `owner`, `lifecycle`, `system`, `providesApis`, `consumesApis`, `dependsOn`, etc.) |
| `.catalog.native.backstage.refs` | object | Referential-integrity results; written only when `backstage_url` is configured |
| `.catalog.native.backstage.refs.domain` | object | `{ name, exists }` for the declared `spec.domain` — present only when a domain is declared and the lookup resolved |
| `.catalog.native.backstage.refs.system` | object | `{ name, exists }` for the declared `spec.system` — same semantics as `refs.domain` |

**Referential integrity.** When `backstage_url` is set, the collector resolves each declared grouping reference against the Backstage catalog API (`GET /api/catalog/entities/by-name/<kind>/<namespace>/<name>`) and records the outcome under `.refs`:

- `spec.domain` → `.refs.domain = { "name": "<value>", "exists": <bool> }`
- `spec.system` → `.refs.system = { "name": "<value>", "exists": <bool> }`

`exists` is `true` on a `200` (the entity was found) and `false` on a `404` (declared but missing). An entry is recorded only when the reference is declared **and** the lookup returns a definitive `200`/`404`. On a transient error (timeout, `5xx`), or when `backstage_url` is unset, the corresponding `.refs` entry is omitted — so downstream checks pend rather than fail on a false negative. The `backstage` policy's `domain-exists` and `system-exists` checks consume these fields.

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `catalog-info` | code | Parses and lints `catalog-info.yaml`; writes parsed metadata and lint results |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/backstage@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   paths: "catalog-info.yaml,catalog-info.yml"  # Customize search paths
```

### Referential integrity (optional)

To cross-check the domain and system declared in `catalog-info.yaml` against a live Backstage catalog, set `backstage_url`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/backstage@v1.0.0
    on: ["domain:your-domain"]
    with:
      backstage_url: "https://backstage.example.com"
      # namespace: "default"   # Backstage namespace to resolve refs in
```

Most internal Backstage deployments require a bearer token. Configure it as a Lunar secret:

```bash
lunar secret set BACKSTAGE_TOKEN <your-token>
```

The collector reads `LUNAR_SECRET_BACKSTAGE_TOKEN` automatically — no extra `with:` is needed. Pair this with the `backstage` policy's `domain-exists` / `system-exists` checks to enforce the results. With `backstage_url` unset (the default), the collector makes no network calls and behaves exactly as the parse-and-lint default above.
