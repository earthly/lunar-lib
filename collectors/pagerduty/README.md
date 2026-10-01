# PagerDuty Collector

Collect on-call schedule and escalation data from the PagerDuty API.

## Overview

This collector queries the PagerDuty REST API to gather on-call schedule,
escalation policy, and service data, writing normalized results to the
`.oncall` category in a tool-agnostic format so the same `oncall` policy works
for PagerDuty, OpsGenie, or any other provider. It ships two trigger variants
that run the same query and write the same data — `oncall` (code hook, on PRs
and the default branch) and `oncall-cron` (daily cron); pick whichever fits
(see Collectors below). The service ID is discovered from the component's
`pagerduty/service-id` meta annotation, an explicit `service_id` input, or —
with `backstage_discovery` enabled — a Backstage annotation, read from the live
catalog (including one inherited from the component's System or Domain) or from
the repo's `catalog-info.yaml`.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.oncall.source` | object | Tool and integration metadata |
| `.oncall.service` | object | PagerDuty service ID, name, status, and `discovered_via`: where the ID came from (see [Service ID discovery](#service-id-discovery)) |
| `.oncall.unmapped` | object | Written instead of `.oncall.service` when every source answered and none maps the component; `searched` lists the places looked. The `oncall` policy's `service-mapped` check fails on it |
| `.oncall.schedule` | object | On-call schedule: exists flag, participant count, rotation type |
| `.oncall.escalation` | object | Escalation policy: exists flag, level count, policy name |
| `.oncall.summary` | object | Summary flags for quick policy evaluation |
| `.oncall.native.pagerduty` | object | Raw PagerDuty API responses |

## Collectors

This integration provides the following collectors — use `include` to select
one (or include both to collect on both triggers). Both run the same query and
write the same `.oncall` data; they differ only in **when** they run.

| Collector | Description |
|-----------|-------------|
| `oncall` | Code hook — queries PagerDuty on pushes to PRs and the default branch, so the on-call guardrail is evaluated as part of a commit/PR check |
| `oncall-cron` | Cron hook — queries PagerDuty daily (04:00 UTC, staggered off the 02:00/03:00 scheduled jobs) and refreshes `.oncall` so the data stays current as schedules rotate, independent of code changes |

Most setups want one or the other. Including **both** is supported and the
normalized `.oncall` data stays correct either way — but be aware the raw arrays
under `.oncall.native.pagerduty` will carry duplicate entries, because Lunar
concatenates arrays written to the same path by different collectors. Guardrail
results are unaffected: the `oncall` policy reads only the normalized scalars.

## Installation

Add to your `lunar-config.yml` (use `include` to pick a trigger variant):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/pagerduty@v1.0.0
    include: [oncall]          # code hook (PRs + default branch); use [oncall-cron] for the daily-cron variant
    on: ["domain:your-domain"]
    # with:
    #   service_id: "PXXXXXX"  # Optional — falls back to catalog meta annotation
```

Secrets:
- `PAGERDUTY_API_KEY` — PagerDuty REST API key (read-only, with service and oncall scopes). Required.
- `BACKSTAGE_TOKEN` — Bearer token for the live Backstage lookup, if your instance needs one. Same secret as the `backstage` collector's.
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` — optional static keys for `backstage_auth_mode: sigv4` on a runner with no IAM role.

(No GitHub token is needed for `backstage_discovery` — `oncall` (code) runs on a fresh checkout and `oncall-cron` sets `clone-code: true`, so either way the collector reads `catalog-info.yaml` from the runner's checkout, not the API.)

### Service ID discovery

The collector resolves the PagerDuty service ID in this order:

1. **Catalog meta annotation** — reads `pagerduty/service-id` from the component's lunar catalog meta. Set via `lunar catalog component --meta pagerduty/service-id <id>`, typically invoked by a company-specific cataloger that knows which components map to which PagerDuty services. This is the recommended approach for orgs where each component has its own service.
2. **Explicit `service_id` input** — set in `lunar-config.yml` for static org-wide configurations, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own service ID).
3. **Live Backstage catalog (opt-in)** — with `backstage_discovery: "true"` and `backstage_url` set, the collector looks up the repo's Component (the first `kind: Component` in its `catalog-info.yaml`, by name and namespace) in the live catalog and reads the [standard PagerDuty annotation](https://support.pagerduty.com/main/docs/backstage-integration-guide) off it (`backstage_annotations`, default `pagerduty.com/service-id,pagerduty/service-id`). If the Component has none, it follows `spec.system` to the System, then the System's `spec.domain` to the Domain, and takes the first ID it finds. So a service declared once on a System or Domain reaches every Component under it, and the Component's own annotation always wins. A bare reference resolves in the namespace of the entity that holds it, as in Backstage.
4. **The checked-out `catalog-info.yaml` (opt-in)** — with `backstage_discovery: "true"`, the annotations in the repo's own file. This is the whole of discovery when `backstage_url` is empty, and the fallback when the live lookup finds nothing or fails. It reads the runner's checkout (the `oncall` code hook clones automatically; `oncall-cron` sets `clone-code: true`), so it needs no token.

   ```yaml
   collectors:
     - uses: github://earthly/lunar-lib/collectors/pagerduty@v1.0.0
       on: ["domain:your-domain"]
       with:
         backstage_discovery: "true"
         backstage_url: "https://backstage.example.com"   # omit to read only catalog-info.yaml
   ```

5. **None found** — the collector writes `.oncall.unmapped` with the places it looked, so the `oncall` policy's `service-mapped` check can fail with that list. If the live lookup failed (an outage, a rejected credential, a response it couldn't read) and nothing else mapped the component, it writes nothing instead: an outage isn't reported as a missing mapping, and the error is in the collector's log.

`.oncall.service.discovered_via` records the source of the ID: `meta:pagerduty/service-id`, `input:service_id`, the Backstage entity it was read from (e.g. `system:default/payment-platform`), or `file:catalog-info.yaml`. When an inherited ID turns out to be wrong, it tells you which entity to fix. It is recorded even when PagerDuty rejects the ID.

The live lookup authenticates like the [`backstage` collector](../backstage/README.md): a `BACKSTAGE_TOKEN` bearer token by default, or AWS SigV4 (`backstage_auth_mode: sigv4`) for a Backstage API behind IAM auth, with the same credential chain, `aws_assume_role_arns` hop and `backstage_ref_lookup` / `backstage_api_path_prefix` options. Its [AWS SigV4 section](../backstage/README.md#aws-sigv4-authentication-iam-role-signed) covers the one-time IAM role setup. The role session is named `lunar-pagerduty-collector`. The walk makes one request per entity it reads, so at most three per run.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `service_id` | *(empty — falls back to catalog meta)* | PagerDuty service ID (e.g. `PXXXXXX`). Optional if `pagerduty/service-id` meta annotation is set. |
| `pagerduty_base_url` | `https://api.pagerduty.com` | PagerDuty API base URL |
| `backstage_discovery` | `"false"` | When `"true"`, find the service ID through Backstage annotations if meta/`service_id` don't provide one: the live catalog when `backstage_url` is set, then the checked-out `catalog-info.yaml`. |
| `backstage_annotations` | `pagerduty.com/service-id,pagerduty/service-id` | Comma-separated annotation keys to read the service ID from (first non-empty wins), tried in order. Only used when `backstage_discovery` is `"true"`. |
| `backstage_catalog_paths` | `catalog-info.yaml,catalog-info.yml` | Comma-separated catalog-info file paths to try in the checked-out repo (first match wins). Only used when `backstage_discovery` is `"true"`. |
| `backstage_url` | *(empty)* | Backstage base URL for the live lookup. Empty skips it. |
| `backstage_api_path_prefix` | `/api` | Path before `/catalog/entities`; `""` when a gateway serves the catalog API at the root. |
| `backstage_auth_mode` | `bearer` | `bearer` (`BACKSTAGE_TOKEN`) or `sigv4` (AWS Signature V4). |
| `backstage_ref_lookup` | `by-name` | `by-name` or `by-query`, for a gateway that only allows the search endpoint. |
| `aws_region` | *(empty)* | SigV4 region; required for `sigv4` unless `AWS_REGION` is set in the pod. |
| `aws_service` | `execute-api` | SigV4 service name (`lambda` for a Lambda function URL). |
| `aws_assume_role_arns` | *(empty)* | Comma-separated roles to `sts:AssumeRole` into before signing; the first one accepted is used. |
