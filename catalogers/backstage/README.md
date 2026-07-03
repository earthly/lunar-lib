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
  - uses: github.com/earthly/lunar-lib/catalogers/backstage@v1.0.0
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
  - uses: github.com/earthly/lunar-lib/catalogers/backstage@v1.1.0
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

### Layering with the GitHub Org Cataloger

For organisations that already run [`github-org`](../github-org) to enumerate repos, run Backstage *after* it so its owner/domain/tag values override the GitHub defaults:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/github-org@v1.0.0
    with:
      org_name: "acme"

  - uses: github.com/earthly/lunar-lib/catalogers/backstage@v1.0.0
    with:
      backstage_url: "https://backstage.example.com"
```

Per Lunar's [merge precedence](../../ai-context/cataloger-reference.md#merge-precedence), catalogers declared later override earlier ones.

### Mapping Components to Repos

Backstage components are matched to Lunar components by reading an annotation on each Backstage Component entity. Defaults assume the standard `github.com/project-slug` annotation:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/backstage@v1.0.0
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

### Owner Format

Backstage `spec.owner` is typically an entity reference like `group:default/team-payments` or `user:default/jane`, **not** an email. By default this cataloger passes the value through verbatim — matching what the existing [`policies/backstage/owner-set`](../../policies/backstage) policy already accepts (`team-payments`, `group:infra`, `user:alice` are all valid).

If you'd rather store bare names, set `owner_format: bare-name` to strip the `<kind>:<namespace>/` prefix. Resolving entity refs to emails by looking up the User/Group entity is intentionally out of scope for v1 — it adds API calls and only works when User/Group entities carry `spec.profile.email`.

`default_owner` is also written verbatim, so you can use whatever convention you prefer (entity ref, email, plain string).

## Source System

This cataloger calls the [Backstage Catalog REST API](https://backstage.io/docs/features/software-catalog/software-catalog-api/) — specifically the `/api/catalog/entities` endpoint. It requires:

1. **Network reach** from the Lunar Runner to the Backstage instance
2. **Authentication** if the instance enforces it — either a bearer token (`LUNAR_SECRET_BACKSTAGE_TOKEN`, the default) or AWS SigV4 signing (`auth_mode: sigv4`; see [AWS SigV4 Authentication](#aws-sigv4-authentication-iam-role-signed))
3. **Read access** to the kinds configured in `entity_kinds`

Pagination is handled automatically; the cataloger streams pages until all matching entities are fetched.
