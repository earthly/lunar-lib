# Backstage Cataloger

Syncs components and domains from a Backstage software catalog into Lunar.

## Overview

This cataloger reads entities from a [Backstage](https://backstage.io) instance via its REST API (`/api/catalog/entities`) and writes them into Lunar. Component entities populate `.components` (with owner, domain, tags); Domain entities populate `.domains` (description, owner). Use this when you run a Backstage instance and want Lunar to inherit its ownership/domain/tag metadata. Pair with the separate [`backstage-catalog-info`](../backstage-catalog-info) cataloger for per-repo `catalog-info.yaml` augmentation (component-cron, layerable). The per-repo [`backstage` collector](../../collectors/backstage) is a different shape entirely — it writes `.catalog.native.backstage` during local / CI Lunar runs.

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

This integration provides the following catalogers:

| Cataloger | Description |
|-----------|-------------|
| `sync` | Fetches entities from the Backstage catalog API and writes Components, Domains (and optionally Systems, APIs, Resources) to the Lunar catalog |

## Hook Type

| Hook | Schedule | Description |
|------|----------|-------------|
| `cron` | `0 2 * * *` | Runs daily at 02:00 UTC |

Daily is the conservative default because a full `/api/catalog/entities` walk paginates through every entity in the Backstage instance — at thousands of components this is a non-trivial fetch against both the Backstage server and the Lunar Runner. Ownership, domain, and tag metadata also change on the order of hours-to-days, not minutes, so a nightly cycle covers the data velocity for almost every catalog. Smaller catalogs are free to tighten the cadence by overriding `hook.schedule` in their forked copy of `lunar-cataloger.yml` — promoting `schedule` to a `with:` input is a candidate v2 if anyone needs per-deployment tunability without a fork.

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

### AWS SigV4 Authentication (IAM-role-signed)

Some Backstage APIs sit behind AWS IAM authentication (commonly Amazon API Gateway) and reject Bearer tokens — every request must carry an AWS Signature V4. Set `auth_mode: sigv4` to sign requests instead of sending a Bearer token:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage@v1.1.0
    with:
      backstage_url: "https://backstage.example.com"
      auth_mode: "sigv4"
      aws_region: "us-east-1"
      aws_service: "execute-api"   # default; API Gateway. Override for other fronting.
```

**No credentials are configured as Lunar secrets, and nothing needs manual rotation.** In `sigv4` mode the cataloger resolves AWS credentials at runtime from the standard AWS credential provider chain and re-resolves them on every run, so short-lived IAM-role credentials always sign with a fresh, valid signature. The chain is tried in this order:

1. **IRSA (EKS) — recommended.** The cataloger pod runs under a service account annotated with an IAM role; EKS injects a web-identity token, which the cataloger exchanges for temporary credentials via STS. The projected token rotates automatically and each run re-exchanges it — zero human involvement.
2. **ECS task role** — the container credentials endpoint (`AWS_CONTAINER_CREDENTIALS_*`).
3. **EC2 instance profile** — IMDSv2 on the node.
4. **Static keys** — only if the `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (/ `AWS_SESSION_TOKEN`) secrets are set. This is an escape hatch for runners with no attached IAM identity; static keys do **not** self-refresh, so prefer one of the role-based sources above.

#### One-time setup: attach the role to the cataloger's service account

Catalogers execute in **operator-spawned snippet pods**, which run under their **own** service account (`OPERATOR_POD_SERVICE_ACCOUNT`, the Lunar chart's `<release>-script-pod`) — *not* the Lunar hub's service account. So annotate **that** service account with the role that is allowed to invoke your Backstage API:

```yaml
# service account used by cataloger/collector/policy snippet pods
metadata:
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/lunar-backstage-sigv4
```

The role's trust policy must allow the snippet-pod service account to assume it, and its permissions must allow `execute-api:Invoke` (or the appropriate action) on your Backstage API. Annotating the hub service account instead is the most common setup mistake — the hub doesn't make the catalog request.

#### Alternative: a standalone `aws-sigv4-proxy` service (no plugin config)

If you'd rather keep signing out of the cataloger entirely, run AWS's [`aws-sigv4-proxy`](https://github.com/awslabs/aws-sigv4-proxy) as its **own** Kubernetes `Deployment` + `Service`, leave `auth_mode: bearer` with no token, and point `backstage_url` at the proxy's in-cluster DNS name:

```yaml
with:
  backstage_url: "http://sigv4-proxy.<namespace>.svc.cluster.local:8080"
```

The proxy signs every forwarded request with **its own** pod's IAM role (IRSA on the proxy Deployment's service account) via the same credential chain, so this self-refreshes too — it just moves signing out of the plugin and into a separate service you operate.

> **Not a same-pod sidecar.** Catalogers run in operator-spawned snippet pods whose container list is fixed by the Lunar operator — one snippet container (which `OPERATOR_SNIPPET_CONTAINER_SPEC_*` *replaces*, it does not append) plus the built-in Lunar sidecar. There is no hook to inject an extra container, so `aws-sigv4-proxy` cannot ride inside the cataloger's pod; it has to be its own Deployment reached over the cluster network. (For purely local testing, you can instead run the proxy on your laptop and point `backstage_url` at `http://host.docker.internal:8080`.)

> A static custom auth header cannot substitute for SigV4 — signatures are per-request and time-bound (they cover an `X-Amz-Date` within a ~15-minute window plus a payload hash), so there is nothing static to configure.

### API Path Prefix

By default the cataloger calls `<backstage_url>/api/catalog/entities`, matching a standard Backstage deployment. Some setups put the catalog API behind a gateway mounted at the root, so the live endpoint is `<backstage_url>/catalog/entities` and the `/api` hop returns `403`/`404`. Set `api_path_prefix` to an empty string to drop the prefix:

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
      api_path_prefix: ""   # gateway is mounted at root — no /api hop
```

`api_path_prefix` defaults to `/api`, so existing configs are unaffected. Any other prefix works too (e.g. `/backstage/api`); the leading slash is optional and a trailing slash is ignored. The resolved endpoint is echoed on the first line of the cataloger's output, so `lunar cataloger dev backstage --verbose` shows exactly which URL it will call.

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

### Verifying Repos Exist (`verify_repos`)

That annotation is a *claim* about a repo, not a fact. Backstage catalogs are maintained by hand, so renamed, deleted and typo'd slugs are routine — and Lunar doesn't validate repo existence when the catalog is saved, so the component gets created anyway and then sits there with nothing behind it: no collector and no policy can ever run against it.

`verify_repos` (on by default) checks each component's repo before writing it and skips the ones that don't exist, naming them in the run log:

```text
github.com: 411/412 repo(s) exist (5 request(s))
Repo does not exist (or GH_TOKEN cannot see it) — skipping:
  github.com/acme/retired-service
Repo verification dropped 1 of 415 component(s)
```

**In practice it's off until you set `GH_TOKEN`** — without the secret the cataloger logs one line and writes every component exactly as before, so upgrading changes nothing until you opt in:

```sh
lunar secret set GH_TOKEN <your-github-token>
```

`Metadata: Read` on a fine-grained PAT or GitHub App installation token is enough (`repo` on a classic PAT). Many lunar-lib plugins reuse the same `GH_TOKEN`, so if you already set it for `github-org` or the GitHub-API collectors this picks it up automatically. Lookups are batched ~100 repos per GraphQL request, so a few thousand components cost a few hundred requests per run rather than one per component.

#### Multiple hosts

The host is read from each component id (`<host>/<owner>/<repo>`), so a catalog spanning github.com and one or more GitHub Enterprise Server hosts needs **no extra configuration** — each host is checked against its own API (`https://<host>/api/graphql`, or `api.github.com` for the public one).

To mix hosts in one catalog, leave `component_id_prefix` empty and let the annotation value carry the host:

```yaml
with:
  component_id_prefix: ""      # annotation value is already ghes.example.com/org/repo
```

#### What happens when it can't tell

Verification is **fail-open, per host**. The catalog only ever shrinks on a repo GitHub positively reports as absent; every "we don't know" leaves things alone:

| Situation | Behaviour |
|---|---|
| No `GH_TOKEN` | Writes everything, logs one line |
| Request fails, or a 200 with an unparseable body | That host's components all kept |
| Nothing resolves for a host | That host's components all kept |

Because hosts are independent, one bad host never affects the others.

**Only GitHub hosts are supported.** Components on any other forge — GitLab, Bitbucket — are left unverified: that host resolves nothing, so it's treated as inconclusive and its components pass through untouched. GitHub components in the same catalog are still verified normally. Note also that a repo the token *cannot see* reads the same as one that doesn't exist, so scope `GH_TOKEN` to every org the catalog references.

Verification covers this cataloger only. The file-based siblings don't need it: [`backstage-catalog-info-monorepo`](../backstage-catalog-info-monorepo) derives ids from repos it enumerated through the GitHub API, and [`backstage-catalog-info`](../backstage-catalog-info) only augments components Lunar already has.

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

### Domain Hierarchy (`subdomainOf` + systems)

Backstage expresses grouping with `spec.subdomainOf` (Domain → Domain) and the `spec.domain` a `System` belongs to. Lunar models domain hierarchy through **dot-notation naming** — `a.b.c` is a child of `a.b` — rather than an explicit parent field. This cataloger bridges the two: it walks the parent chain and keys each domain by its full dotted path.

- **Domains** are keyed by their full `spec.subdomainOf` ancestry: a domain `c` that is `subdomainOf` `b`, itself `subdomainOf` `a`, is written as `a.b.c`.
- **Systems** are treated as the deepest grouping level — a `System` is nested as a subdomain of the domain it belongs to (`spec.domain`), keyed `<domain-path>.<system-name>`.
- **Components** resolve their `domain` to the full dotted path of their `spec.system` (or `spec.domain` when no system is set).

A catalog that doesn't use these fields is unaffected: a `Domain` with no `subdomainOf`, or a `System` with no `spec.domain`, is keyed by its bare `metadata.name` — byte-for-byte what a flat sync produced. The hierarchy only surfaces where Backstage actually expresses it, which is why there is no "flat vs nested" switch: nesting *is* the faithful mapping, and it degrades to flat exactly when there's nothing to nest.

```yaml
catalogers:
  - uses: github://earthly/lunar-lib/catalogers/backstage@v1.2.0
    with:
      backstage_url: "https://backstage.example.com"
      entity_kinds: "Component,Domain,System"   # include System to nest systems under their domain
```

Given a Backstage catalog like:

```
commerce                     (Domain, top — no subdomainOf)
 └─ payments                 (Domain, subdomainOf commerce)
     └─ ledger               (Domain, subdomainOf payments)
         └─ billing          (System, spec.domain: ledger)
             └─ invoicing-api (Component, spec.system: billing)
```

the cataloger produces:

```json
{
  "domains": {
    "commerce": { "description": "…", "owner": "…" },
    "commerce.payments": { "description": "…", "owner": "…" },
    "commerce.payments.ledger": { "description": "…", "owner": "…" },
    "commerce.payments.ledger.billing": { "description": "…", "owner": "…" }
  },
  "components": {
    "github.com/acme/invoicing-api": {
      "owner": "group:default/team-billing",
      "domain": "commerce.payments.ledger.billing",
      "tags": ["bs-type-service", "bs-lifecycle-production"]
    }
  }
}
```

The same component synced from a catalog with no `subdomainOf` / system links would instead get `domain: "billing"`, alongside bare `commerce` / `payments` / `ledger` / `billing` domains — the pre-hierarchy behavior, unchanged.

**Notes & caveats**

- **Upgrade note.** If you already run this cataloger against a Backstage instance that *does* use `subdomainOf` or systems-under-domains, upgrading re-keys those domains from bare names (`billing`) to dotted paths (`commerce.payments.ledger.billing`), and any policy or initiative that targets them by name must be updated to the new key. Catalogs with no hierarchy links are unaffected — their keys don't change.
- **Sync the parent kinds.** Parent resolution only sees entities the cataloger fetched, so include every level in `entity_kinds` (e.g. `Component,Domain,System`). A `subdomainOf` / `spec.domain` reference to an entity that wasn't synced falls back to the bare name for that hop, and the gap is logged.
- **Entity refs are normalised.** `subdomainOf` / `spec.domain` / `spec.system` values such as `domain:default/payments` are stripped to their bare name (`payments`) before joining.
- **Separator.** Path segments join with `.`, Lunar's hierarchy separator. Backstage names that themselves contain a `.` are rare and would be indistinguishable from a level boundary; hyphenated names (`payment-gateway`) are unaffected.
- **Dangling or cyclic chains.** A missing parent stops the walk (partial path, logged); a cycle is broken defensively so a malformed catalog can't hang the run.

### Filtering Entities

Most of the time you'll want your whole catalog in Lunar. But there are cases where you don't need *everything* at once — two common ones:

- **Onboard incrementally** — bring one domain live today (say `platform-engineering`), the next tomorrow, instead of syncing thousands of components in one shot.
- **Cut noise** — sync only production services, not experimental libraries; or exclude a single problem component while you sort it out.

The cataloger exposes structured `include_*` / `exclude_*` inputs for exactly this, plus a raw-expression escape hatch.

#### By type and lifecycle

Filter on the Backstage `spec.type` and `spec.lifecycle` fields:

```yaml
with:
  include_types: "service"                 # only services — drop libraries, websites, …
  include_lifecycles: "production"         # only production — drop experimental / deprecated
  exclude_types: "library"                 # or start from "everything" and subtract
```

- `include_types` / `include_lifecycles` are **allowlists** — non-empty means "sync only these values".
- `exclude_types` / `exclude_lifecycles` are **denylists** — "sync everything except these".
- All are comma-separated and **case-insensitive**; empty (the default) disables the filter.
- An entity with **no value** for the field is left alone — a `Resource` (which has no `spec.lifecycle`) is never dropped by a lifecycle filter, and non-component kinds are untouched. See [Semantics](#semantics-all-structured-filters).

#### By domain and system (phased onboarding)

```yaml
with:
  include_domains: "platform-engineering"  # go-live one domain at a time
```

`include_domains` / `exclude_domains` match each component's **resolved** domain path — the same dotted value written to `.components[*].domain` (see [Domain Hierarchy](#domain-hierarchy-subdomainof--systems)). A filter value matches exactly **or** as a dotted-prefix ancestor: `commerce` matches `commerce`, `commerce.payments`, and everything nested beneath. `include_systems` / `exclude_systems` match a component's `spec.system` by bare name.

These are **membership** filters: a component with no resolved domain (or no system) isn't a member of anything, so an `include_domains` / `include_systems` allowlist excludes it. (An `exclude_*` denylist leaves it alone — there's nothing to match.)

The referenced `Domain` and `System` entities are always synced regardless of these filters, so the components that *do* pass still resolve their domain refs (the hub's `validateDomainRefs` stays satisfied). Onboarding one domain therefore leaves the *other* domains present but empty — harmless catalog structure, not dangling refs.

#### Semantics (all structured filters)

| Rule | Behavior |
|------|----------|
| **Empty = disabled** | An unset `include_*`/`exclude_*` never filters anything. |
| **Exclude wins over include** | An entity matching both an allowlist and a denylist is **dropped** — same precedence as github-org's `allowed_topics` / `disallowed_topics`. |
| **Type/lifecycle — absence passes** | Attribute filters. An entity with no value for the field isn't judged by it: a `Resource` (no `spec.lifecycle`) survives a lifecycle filter, and `Domain`/`System` are never touched — so the hierarchy always survives even when components are filtered down. |
| **Domain/system — absence = non-member** | Membership filters. For an `include_*`, a component with no resolved domain/system is excluded (it's in no group). An `exclude_*` leaves it alone (nothing to match). |
| **Client-side** | Applied after the fetch. Backstage's `?filter=` supports equality/existence but **no negation**, so exclude can't be pushed server-side; for consistency include isn't either. The run logs how many candidate components the filters dropped. |

> **Scale caveat.** Structured filters run **after** the full catalog walk — they shrink what's *written to Lunar*, not what's *fetched from Backstage*. On a very large instance the paginated fetch still pulls every entity before filtering. To also trim the API payload, add a server-side `filter` (below) or a `namespace`. Pushing `include_types` down to the server is a candidate optimization, but it can't be applied naively to a multi-kind sync (it would also drop the `Domain`/`System` entities that carry no `spec.type`), so it's deferred.

#### Raw filter escape hatch

For anything the structured inputs don't cover, pass a raw [Backstage filter expression](https://backstage.io/docs/features/software-catalog/software-catalog-api/#get-entities) through `filter`. Unlike the structured filters this runs **server-side**, so it also trims the fetch:

```yaml
with:
  filter: "metadata.annotations.team=platform"
```

The raw `filter` and the structured filters compose: the raw filter narrows the fetch, the structured filters refine the result.

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. Resolving entity refs to emails by looking up the User/Group entity is intentionally out of scope for v1 — it adds API calls and only works when User/Group entities carry `spec.profile.email`.

`default_owner` is also written verbatim, so you can use whatever convention you prefer (entity ref, email, plain string).

## Source System

This cataloger calls the [Backstage Catalog REST API](https://backstage.io/docs/features/software-catalog/software-catalog-api/) — specifically the `/catalog/entities` endpoint, reached at `<backstage_url>/api/catalog/entities` by default (see [API Path Prefix](#api-path-prefix) to change the `/api` segment). It requires:

1. **Network reach** from the Lunar Runner to the Backstage instance
2. **Authentication** if the instance enforces it — either a bearer token (`LUNAR_SECRET_BACKSTAGE_TOKEN`, the default) or AWS SigV4 signing (`auth_mode: sigv4`; see [AWS SigV4 Authentication](#aws-sigv4-authentication-iam-role-signed))
3. **Read access** to the kinds configured in `entity_kinds`

Pagination is handled automatically; the cataloger streams pages until all matching entities are fetched.

When `verify_repos` is on (the default) it additionally calls the [GitHub GraphQL API](https://docs.github.com/en/graphql) — one batched query per ~100 repos, resolving each candidate component's `<owner>/<repo>` — and needs:

- **`GH_TOKEN` secret** with repository metadata read access on every org the Backstage catalog references. A repo the token cannot see is reported as absent, so an under-scoped token drops real components.
- **Network reach** from the Lunar Runner to each host in the catalog (`api.github.com`, plus `https://<host>/api/graphql` for any GitHub Enterprise Server host).

See [Verifying Repos Exist](#verifying-repos-exist-verify_repos) for the fail-open behaviour when either is missing.
