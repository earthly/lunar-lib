# Backstage Collector

Parses and lints Backstage `catalog-info.yaml` files.

## Overview

This collector scans the repository for a Backstage catalog definition file (`catalog-info.yaml` or `catalog-info.yml`), parses it, and lints it for schema/syntax issues. The raw Backstage descriptor (apiVersion, kind, metadata, spec) is written to the `.catalog.native.backstage` Component JSON path as-is — annotations keep their original `backstage.io/` or vendor prefixes. Files that declare [multiple entities](#multiple-entities) separated by `---` are fully supported. The search paths are configurable via the `paths` input.

Optionally, when a `backstage_url` is configured, it cross-checks the referenced domain and system against the live catalog under `.catalog.native.backstage.refs`, and resolves entity-reference tags on infrastructure into `.catalog.entity_refs`.

## Collected Data

When a catalog-info file is found, this collector writes to the following Component JSON paths. When no file is found, the `.catalog.native.backstage` namespace is **not written** — absence of the namespace is the signal.

| Path | Type | Description |
|------|------|-------------|
| `.catalog.native.backstage.valid` | boolean | Whether the catalog-info file passed lint/schema checks |
| `.catalog.native.backstage.errors[]` | array | Lint findings (each with `line`, `message`, `severity`) |
| `.catalog.native.backstage.path` | string | Relative path to the file that was parsed |
| `.catalog.native.backstage.apiVersion` | string | Backstage API version of the [primary entity](#multiple-entities) (e.g. `backstage.io/v1alpha1`) |
| `.catalog.native.backstage.kind` | string | Kind of the [primary entity](#multiple-entities) (e.g. `Component`, `System`, `API`) |
| `.catalog.native.backstage.metadata` | object | Raw `metadata` block of the primary entity (`name`, `description`, `annotations`, `tags`, etc.) |
| `.catalog.native.backstage.spec` | object | Raw `spec` block of the primary entity (`type`, `owner`, `lifecycle`, `system`, `providesApis`, `consumesApis`, `dependsOn`, etc.) |
| `.catalog.native.backstage.entities[]` | array | Every entity declared in the file (each with its own `valid`, `errors`, `apiVersion`, `kind`, `metadata`, `spec`). A single-entity file yields one element |
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

### Entity references on infrastructure resources (`.catalog.entity_refs`)

The `entity-refs` sub-collector resolves Backstage entity references that were tagged onto infrastructure resources. It is the Backstage-specific counterpart to generic IaC tag collection: the [`terraform` collector](../terraform/README.md) records resource tags without assigning meaning to any key, and this sub-collector interprets one of those keys as a Backstage entity reference.

| Path | Type | Description |
|------|------|-------------|
| `.catalog.entity_refs` | object | Resolution results; written only when `backstage_url` is set **and** IaC tag data is present |
| `.catalog.entity_refs.checked` | boolean | `true` whenever resolution ran — the signal the policy uses to tell *configured* from *not configured* |
| `.catalog.entity_refs.source` | object | Tool metadata (`tool: backstage`, `integration: api`) |
| `.catalog.entity_refs.refs[]` | array | One entry per distinct concrete reference: `{name, exists, resources[]}` on a definitive lookup, or `{name, error, resources[]}` on a transient failure |
| `.catalog.entity_refs.unresolved[]` | array | Tag values that were unresolved Terraform expressions: `{value, resources[]}` — nothing concrete to look up |

How it works:

- Fires on the **`after-json`** hook with `path: .iac.modules`, so it runs at the doneness gate once an IaC collector has written its normalized modules. It reads the merged Component JSON via `lunar component get-json` — no repo checkout needed.
- Collects every distinct value of the `entity_ref_tag_key` tag across `.iac.modules[].resources[].tags` and `.iac.modules[].default_tags`, then resolves each **once** against `GET /api/catalog/entities/by-name/<kind>/<namespace>/<name>`. Deduplicating means one lookup per reference no matter how many resources share it.
- `exists` is `true` on a `200` and `false` on a `404`. A transient failure (timeout, `5xx`) records `error` instead, so a Backstage outage stays distinguishable from a real miss and the policy skips rather than fails.
- `resources[]` lists the `<type>.<name>` resources carrying the reference, so a policy failure can name the offending resources.
- A value like `${var.entity_ref}` is an unresolved Terraform expression — `hcl2json` never runs `terraform plan`, so there is no concrete value. Those are reported under `unresolved[]` and never looked up.
- Namespace resolution mirrors Backstage's own: a qualified ref (`ns/name`) carries its own namespace, a bare ref uses `default`.
- When `backstage_url` is unset, or the component has no IaC tag data, nothing is written and the policy's `entity-ref-valid` check skips (passes).

> **Why `.catalog.entity_refs` and not `.catalog.native.backstage.*`?** The presence of `.catalog.native.backstage` is the "a `catalog-info.yaml` exists" signal that several checks (`catalog-info-exists`, `owner-set`, `lifecycle-set`, …) key off. Writing entity-ref results under it would make that object exist on a repo with no catalog file, silently flipping those checks. `.catalog.entity_refs` sits at the normalized category level alongside `.catalog.entity` and `.catalog.annotations`, so the two concerns stay independent.

### Multiple entities

A single `catalog-info.yaml` may declare several Backstage entities separated by `---` — most commonly a `Component` plus the `API`s it provides, or a `System` and its `Component`s. The collector parses **every** document in the file:

- **`valid` / `errors[]` aggregate across all entities.** The file is `valid` only when every entity passes lint; each error message in a multi-entity file is prefixed with a `document N (Kind 'name')` locator (and carries an `entity` index into `entities[]`) so you can tell which document is at fault.
- **`entities[]` lists all of them,** each with its own `valid`/`errors`/`apiVersion`/`kind`/`metadata`/`spec`.
- **The primary entity is hoisted to the top level.** `.apiVersion`, `.kind`, `.metadata`, and `.spec` mirror the first `Component` in the file (or the first document when there is no `Component`). The single-entity policies — `owner-set`, `lifecycle-set`, `system-set`, `required-annotations`, the tag-pattern checks, and the referential-integrity lookups — read these paths, so they operate on that primary `Component` (owner, lifecycle, and system are `Component`-level fields in Backstage). A single-entity file behaves exactly as before: one element in `entities[]`, that entity hoisted.

### Lint checks

The `valid` / `errors[]` fields above come from a lint that mirrors the rules the Backstage **server** enforces on ingest, so violations surface in CI (via the `backstage` policy's `catalog-info-valid` check) instead of failing silently at registration. It reports:

- `apiVersion` present, a string, and starting with `backstage.io/`
- `kind` present, a string, and a known entity kind
- `metadata.name` present, a string, and DNS-compatible
- **`metadata.tags` — each tag valid.** Backstage requires each tag to be lowercase `[a-z0-9+#]` segments joined by single dashes, at most 63 characters (`Validators.isValidTag`). The `catalog-info.yaml` schema itself accepts any string, so a tag like `hosting/internal` parses fine but the Backstage server **rejects the whole entity** at ingest (`"tags.0" is not valid; expected a string that is sequences of [a-z0-9+#] separated by [-]`). The lint flags such tags as errors — use dashes instead (e.g. `hosting-internal`).
- `spec` present (a mapping) for non-`Location` kinds

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `catalog-info` | code | Parses and lints `catalog-info.yaml`; writes parsed metadata and lint results |
| `entity-refs` | after-json | Resolves Backstage entity-reference tags on infrastructure resources into `.catalog.entity_refs`; requires `backstage_url` |

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

### Entity-reference tags on infrastructure (optional)

The same `backstage_url` also enables the `entity-refs` sub-collector, which resolves the entity-reference tag on infrastructure resources. Pair it with an IaC collector that records resource tags:

```yaml
collectors:
  # Records resource tags generically — knows nothing of Backstage
  - uses: github://earthly/lunar-lib/collectors/terraform@main
    on: [infra]

  # Interprets one of those tag keys as a Backstage entity reference
  - uses: github://earthly/lunar-lib/collectors/backstage@v1.0.0
    on: [infra]
    with:
      backstage_url: "https://backstage.example.com"
      entity_ref_tag_key: "backstage.com/entity_ref"   # the default
```

Results land in `.catalog.entity_refs`; enforce them with the `backstage` policy's `entity-ref-valid` check. Use `include: [entity-refs]` / `exclude: [entity-refs]` to run this sub-collector on its own or opt out of it.

> **`entity-refs` needs a Hub with the `after-json` hook.** Without it, `exclude: [entity-refs]`; the `catalog-info` sub-collector works on any Hub.
