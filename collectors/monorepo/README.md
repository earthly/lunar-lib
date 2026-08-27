# Monorepo Collector

Distributes repo-scoped scan results to a monorepo's subcomponents.

## Overview

Some scanners are inherently repository-scoped — CodeQL default setup analyses a
whole repository and reports findings tagged with a repo-relative file path. In
a monorepo the Lunar components are the subdirectories while the scan resolves
to the repository, so the findings land on the repo-root component and every
subcomponent reads as "No SAST scanning data found" despite having been scanned.
Enabled on the root component, this collector redistributes those findings to
the subcomponents by file path, writing each one's own slice onto its Component
JSON at the same commit. Attribution reuses the same path rules the Hub already
applies to decide which components a changed file affects, so no new
configuration concept is introduced and nothing in CI has to change.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sast.issues[]` | array | *(on each subcomponent)* The repo-wide findings whose file belongs to that subcomponent |
| `.sast.findings` | object | *(on each subcomponent)* Severity counts recomputed for that subset |
| `.sast.summary` | object | *(on each subcomponent)* Summary booleans (has_critical, has_high) for that subset |
| `.sast.source` | object | *(on each subcomponent)* The root's scanner metadata, stamped `integration: "monorepo-fanout"` |
| `.sast.native.monorepo_fanout` | object | Provenance — on a subcomponent: root component, root SHA, paths used, matched count, fingerprint. On the root: the per-target written/skipped breadcrumb |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `sast-fanout` | Runs on the repository ROOT via the `after-json` hook on `.sast.issues`, and redistributes the root's repo-wide SAST findings to its subcomponents by file path. Targets are discovered from the catalog (every component whose name is prefixed by the root's) or pinned with the `subcomponents` input. A finding reaches a subcomponent when its file matches that subcomponent's patterns — the explicit `paths:` plus the implicit `<subdir>/*` its name implies — so a shared file two subcomponents both claim reaches both, and a finding nothing claims stays on the root. A subcomponent with zero matches is still written with `total: 0`, which is what turns its SAST policy from "no data" into a pass; a subcomponent that already has SAST data of its own is never overwritten. Requires Hub v3.3.0+ (the `after-json` hook), and because the wave is fire-once per `(component, sha, pr)`, re-testing needs a fresh commit |

## Installation

Add to your `lunar-config.yml`. Three things have to be true first:

1. the monorepo's **root** needs a component of its own;
2. a scanner that writes `.sast.issues` has to be enabled on that root — the
   `codeql` collector's `cicd` sub-collector does this from the SARIF that
   `codeql database interpret-results` leaves on disk, so enabling
   `collectors/codeql` on the same root is the usual pairing;
3. **at least one policy must also evaluate the root.** An `after-json`
   collector is dispatched by the Hub's doneness gate, and that gate is only
   consulted while bundling a component's policies — so a component that no
   policy evaluates never fires its after-json collectors at all. Watch out for
   the interaction with domains: a policy declared with no `on:` resolves to
   `domain:other`, so putting the root in a dedicated domain (sensible, and
   recommended below) can silently take it out of every fleet policy's scope
   and leave it with none.

```yaml
components:
  # Define a component for the ROOT of the monorepo. It exists so the repo-wide
  # scan has somewhere to land and the fan-out has somewhere to run. Giving it
  # its own domain keeps your service guardrails off it — the root is a scan
  # carrier, not a deployable service.
  github.com/acme/repo:
    owner: platform@acme.com
    domain: engineering.monorepo-roots
    branch: "main"

  # Subcomponents stay exactly as they are — nothing about them changes.
  github.com/acme/repo/services/api:
    domain: engineering.services
    paths: ["services/api/*"]

collectors:
  # The fan-out, on the root — alongside whichever collector produces the
  # repo-wide findings there.
  - uses: github://earthly/lunar-lib/collectors/monorepo@v1.13.0
    on: ["component:github.com/acme/repo"]
    # with:
    #   subcomponents: ""      # pin the target list, skipping catalog discovery
    #   max_subcomponents: "50"

policies:
  # Point 3 above: the root needs a policy of its own, or its after-json
  # collectors are never dispatched. `sast.executed` is the natural one — it
  # asserts the repo-wide scan actually ran.
  - uses: github://earthly/lunar-lib/policies/sast@v1.13.0
    on: ["component:github.com/acme/repo"]
    include: [executed]
```
