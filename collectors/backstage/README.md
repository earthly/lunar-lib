# Backstage Collector

Parses and lints Backstage `catalog-info.yaml` files.

## Overview

This collector scans the repository for a Backstage catalog definition file (`catalog-info.yaml` or `catalog-info.yml`), parses it, and lints it for schema/syntax issues. The raw Backstage descriptor (apiVersion, kind, metadata, spec) is written to the `.catalog.native.backstage` Component JSON path as-is — annotations keep their original `backstage.io/` or vendor prefixes. Files that declare [multiple entities](#multiple-entities) separated by `---` are fully supported. The search paths are configurable via the `paths` input.

Optionally, when a `backstage_url` is configured, it also cross-checks the domain and system referenced in `catalog-info.yaml` against the live Backstage catalog and records whether those entities exist under `.catalog.native.backstage.refs`.

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

### AWS SigV4 Authentication (IAM-role-signed)

Some Backstage APIs sit behind AWS IAM authentication (commonly Amazon API Gateway) and reject Bearer tokens — every request must carry an AWS Signature V4. Set `auth_mode: sigv4` to sign the referential-integrity lookups instead of sending a Bearer token:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/backstage@v1.0.0
    on: ["domain:your-domain"]
    with:
      backstage_url: "https://backstage.example.com"
      auth_mode: "sigv4"
      aws_region: "us-east-1"
      aws_service: "execute-api"   # default; API Gateway. Override for other fronting.
```

**No credentials are configured as Lunar secrets, and nothing needs manual rotation.** In `sigv4` mode the collector resolves AWS credentials at runtime from the standard AWS credential provider chain and re-resolves them on every run, so short-lived IAM-role credentials always sign with a fresh, valid signature. The chain is tried in this order:

1. **IRSA (EKS) — recommended.** The pod runs under a service account annotated with an IAM role; EKS injects a web-identity token, which the collector exchanges for temporary credentials via STS. The projected token rotates automatically and each run re-exchanges it — zero human involvement.
2. **EKS Pod Identity / ECS task role** — the container credentials endpoint (`AWS_CONTAINER_CREDENTIALS_*`).
3. **EC2 instance profile** — IMDSv2 on the node.
4. **Static keys** — only if the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (/ `AWS_SESSION_TOKEN`) secrets are set. This is an escape hatch for runners with no attached IAM identity; static keys do **not** self-refresh, so prefer one of the role-based sources above.

#### One-time setup: attach the role to the snippet pod's service account

`catalog-info` is a **`code`-hook** collector, so it executes on a Lunar Runner in **operator-spawned snippet pods** — not in your CI pipeline, and not under the Lunar hub's service account. Those pods run under `OPERATOR_POD_SERVICE_ACCOUNT` (the Lunar chart's `<release>-script-pod`), so annotate **that** service account with the role allowed to invoke your Backstage API:

```yaml
# service account used by cataloger/collector/policy snippet pods
metadata:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/lunar-backstage-sigv4
```

The role's trust policy must allow the snippet-pod service account to assume it, and its permissions must allow `execute-api:Invoke` (or the appropriate action) on your Backstage API. Annotating the hub service account instead is the most common setup mistake — the hub doesn't make the catalog request.

> **Already using SigV4 with the [Backstage cataloger](../../catalogers/backstage/README.md)?** Then this is already done. Both plugins run in the same snippet pods under the same service account, so one role annotation covers both — set `auth_mode: sigv4` here and it just works.

#### Failure modes

Parsing and linting are the collector's primary job and are **never** discarded because of an auth problem. If credentials can't be resolved, `aws_region` is missing, or the signed request is rejected, the collector still writes the full parse/lint result and records the reference lookup as a non-definitive `{name, error}`:

```json
"refs": {
  "checked": true,
  "domain": { "name": "payments", "error": "aws_region required for sigv4" }
}
```

The `backstage` policy treats `{name, error}` as "couldn't determine" rather than "doesn't exist", so a misconfiguration shows up as an unresolved check rather than a false `domain-exists` failure. The underlying error is also logged to the collector's stderr.

> A static custom auth header cannot substitute for SigV4 — signatures are per-request and time-bound (they cover an `X-Amz-Date` within a ~15-minute window plus a payload hash), so there is nothing static to configure.
