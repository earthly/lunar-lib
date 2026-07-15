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
| `.catalog.native.backstage.refs` | object | Referential-integrity results; written (as an object) only when `backstage_url` is configured |
| `.catalog.native.backstage.refs.checked` | boolean | `true` whenever `backstage_url` is set — the "referential integrity ran" signal the policy keys off to distinguish *configured* from *not configured* |
| `.catalog.native.backstage.refs.domain` | object | For the declared `spec.domain`: `{ name, exists }` when the lookup resolved (200/404), or `{ name, error }` on a transient failure. Absent when no domain is declared |
| `.catalog.native.backstage.refs.system` | object | For the declared `spec.system` — same semantics as `refs.domain` |

**Referential integrity.** When `backstage_url` is set, the collector resolves each declared grouping reference against the Backstage catalog API (`GET /api/catalog/entities/by-name/<kind>/<namespace>/<name>`) and records the outcome under `.refs`. The `<namespace>` is taken from the reference itself — a qualified ref (`ns/name`) carries its own, otherwise the component's own `metadata.namespace` is used, falling back to `default`, so there is no namespace input to configure:

- `.refs.checked = true` — always written when `backstage_url` is set, regardless of what (if anything) is declared. This is the signal the policy uses to tell "collector configured" from "not configured."
- `spec.domain` → `.refs.domain = { "name": "<value>", "exists": <bool> }` on a definitive lookup, or `{ "name": "<value>", "error": "<reason>" }` on a transient failure.
- `spec.system` → `.refs.system` — same shape and semantics as `refs.domain`.

`exists` is `true` on a `200` (the entity was found) and `false` on a `404` (declared but missing). A per-reference entry is written only when that reference is **declared**; an undeclared ref has no entry. On a transient error (timeout, `5xx`) the entry is written with an `error` field instead of `exists`, so a Backstage outage stays distinguishable from a real miss — the policy skips (passes) an errored ref rather than failing it. When `backstage_url` is unset, `.refs` is not written at all (no `checked` marker), and the policy's referential-integrity checks skip (pass) because there is nothing to verify. The `backstage` policy's `domain-exists` and `system-exists` checks consume these fields.

> **Backstage entity model.** In Backstage, `spec.system` lives on `Component` entities (a component belongs to a system) while `spec.domain` lives on `System` entities (a system belongs to a domain). So `system-exists` is the check that fires for the common one-`Component`-per-repo case, and `domain-exists` applies to repos whose `catalog-info.yaml` is itself a `kind: System` (or a `Component` that carries a custom `spec.domain`). Each check only does work when its reference is actually declared.

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
```

Most internal Backstage deployments require a bearer token. Configure it as a Lunar secret:

```bash
lunar secret set BACKSTAGE_TOKEN <your-token>
```

The collector reads `LUNAR_SECRET_BACKSTAGE_TOKEN` automatically — no extra `with:` is needed. Pair this with the `backstage` policy's `domain-exists` / `system-exists` checks to enforce the results. With `backstage_url` unset (the default), the collector makes no network calls and behaves exactly as the parse-and-lint default above.
