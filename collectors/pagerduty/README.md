# PagerDuty Collector

Collect on-call schedule and escalation data from the PagerDuty API.

## Overview

This collector queries the PagerDuty REST API to gather on-call schedule,
escalation policy, and service data, writing normalized results to the
`.oncall` category in a tool-agnostic format so the same `oncall` policy works
for PagerDuty, OpsGenie, or any other provider. It runs on push (`oncall`), on a
daily cron (`oncall-cron`), or once the backstage collector's live catalog
lookup lands (`backstage`); see Collectors below. The service ID comes from the
component's `pagerduty/service-id` meta annotation, an explicit `service_id`
input, or, with `backstage_discovery`, a Backstage annotation, including one
inherited from the component's System or Domain.

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

This integration provides the following collectors (use `include` to select a
subset). All three write the same `.oncall` data; they differ in **when** they
run and where they look for the service ID.

| Collector | Description |
|-----------|-------------|
| `oncall` | Code hook — queries PagerDuty on pushes to PRs and the default branch, so the on-call guardrail is evaluated as part of a commit/PR check |
| `oncall-cron` | Cron hook — queries PagerDuty daily (04:00 UTC, staggered off the 02:00/03:00 scheduled jobs) and refreshes `.oncall` so the data stays current as schedules rotate, independent of code changes |
| `backstage` | After-json hook — with `backstage_discovery: live`, reads the service ID from the backstage collector's live catalog lookup once it lands in the Component JSON, then queries PagerDuty |

Including both `oncall` and `oncall-cron` is supported and the normalized
`.oncall` data stays correct — but be aware the raw arrays under
`.oncall.native.pagerduty` will carry duplicate entries, because Lunar
concatenates arrays written to the same path by different collectors. Guardrail
results are unaffected: the `oncall` policy reads only the normalized scalars.
On push, exactly one of `oncall` and `backstage` writes for a given component.

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

### Service ID discovery

The collector resolves the PagerDuty service ID in this order:

1. **Catalog meta annotation** — reads `pagerduty/service-id` from the component's lunar catalog meta. Set via `lunar catalog component --meta pagerduty/service-id <id>`, typically invoked by a company-specific cataloger that knows which components map to which PagerDuty services.
2. **Explicit `service_id` input** — set in `lunar-config.yml` for static org-wide configurations, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own service ID).
3. **Backstage (opt-in)** — the [standard PagerDuty annotation](https://support.pagerduty.com/main/docs/backstage-integration-guide) (`backstage_annotations`, default `pagerduty.com/service-id,pagerduty/service-id`), from one of two places:
   - `backstage_discovery: "true"` reads the repo's checked-out `catalog-info.yaml`. It needs no token: the `oncall` code hook clones automatically, and `oncall-cron` sets `clone-code: true`.
   - `backstage_discovery: live` reads what the [backstage collector](../backstage/README.md) found in the live catalog, so a service declared once on a System or Domain reaches every Component under it. It takes the Component's own annotation first, then its System's, then that System's Domain's, then the catalog file's. Only the backstage collector calls Backstage, with its own auth (bearer or SigV4, including `aws_assume_role_arns`); the pagerduty collector needs no Backstage secret.
4. **None found** — the collector writes `.oncall.unmapped` with the places it looked, so the `oncall` policy's `service-mapped` check can fail with that list. If a Backstage lookup failed (an outage, a rejected credential, a response that couldn't be read) and nothing else mapped the component, it writes nothing instead: an outage isn't reported as a missing mapping, and the error is in the collector's log.

`.oncall.service.discovered_via` records the source of the ID: `meta:pagerduty/service-id`, `input:service_id`, the Backstage entity it was read from (e.g. `system:default/payment-platform`), or `file:catalog-info.yaml`. When an inherited ID turns out to be wrong, it tells you which entity to fix. It is recorded even when PagerDuty rejects the ID.

### Live Backstage lookup

`backstage_discovery: live` needs the backstage collector on the same components with `backstage_url` set, and the `backstage` sub-collector (included unless you `include:` a subset):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/backstage@v1.0.0
    on: ["domain:your-domain"]
    with:
      backstage_url: "https://backstage.example.com"
  - uses: github://earthly/lunar-lib/collectors/pagerduty@v1.0.0
    on: ["domain:your-domain"]
    with:
      backstage_discovery: "live"
```

- The `backstage` sub-collector runs once the backstage collector's lookup (`.catalog.native.backstage.refs.entity`) is in the Component JSON. The JSON it reads can lag that write by several minutes, so it retries the read for up to `backstage_wait_seconds` (1800 by default), backing off up to 60s between attempts, then fails the run. The `oncall` checks wait for it.
- `oncall` still collects components mapped by meta or `service_id`, and leaves the rest to `backstage`. `oncall-cron` reads the backstage collector's lookup from the default branch's Component JSON.
- The System and Domain are the ones the catalog file declares (`spec.system`, and that System's `spec.domain`), which the backstage collector also checks for referential integrity. A Component missing from the catalog still inherits from the System its file declares.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `service_id` | *(empty — falls back to catalog meta)* | PagerDuty service ID (e.g. `PXXXXXX`). Optional if `pagerduty/service-id` meta annotation is set. |
| `pagerduty_base_url` | `https://api.pagerduty.com` | PagerDuty API base URL |
| `backstage_discovery` | `"false"` | Where to look when meta and `service_id` don't give an ID: `"false"` nowhere, `"true"` the checked-out `catalog-info.yaml`, `"live"` the backstage collector's live catalog lookup. |
| `backstage_annotations` | `pagerduty.com/service-id,pagerduty/service-id` | Comma-separated annotation keys to read the service ID from, tried in order. Used when `backstage_discovery` is `"true"` or `"live"`. |
| `backstage_catalog_paths` | `catalog-info.yaml,catalog-info.yml` | Comma-separated catalog-info file paths to try in the checked-out repo (first match wins). Only used when `backstage_discovery` is `"true"`. |
| `backstage_wait_seconds` | `1800` | How long the `backstage` sub-collector retries reading the backstage collector's lookup before failing the run. |
