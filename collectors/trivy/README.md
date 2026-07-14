# Trivy Vulnerability Scanner Collector

Scans source code dependencies for known vulnerabilities using Trivy.

## Overview

This collector runs Trivy filesystem scans against repository source code to detect known CVEs in dependencies. It supports all ecosystems Trivy covers (Go, Node.js, Python, Java, Rust, Ruby, PHP, .NET, etc.) and writes normalized vulnerability data to `.sca` in the Component JSON, making results immediately consumable by the existing SCA policy. A scheduled `rescan` re-runs the same scan on a cron and overwrites `.sca`, so a previously-clean commit is re-evaluated against CVEs published after it was first scanned. Prior re-scans can optionally be kept in a bounded `.sca.history[]` for point-in-time audit (off by default).

No secrets or vendor accounts are required — Trivy's vulnerability database is downloaded at scan time to ensure the latest CVE data.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sca.source` | object | Source metadata (tool name, version, integration method, and `collected_at` scan timestamp) |
| `.sca.vulnerabilities` | object | Severity counts (critical, high, medium, low, total) |
| `.sca.findings[]` | array | Individual vulnerability findings with CVE, package, fix info |
| `.sca.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.sca.history[]` | array | *(opt-in)* Bounded list of prior scan snapshots (source, counts, summary) for point-in-time audit; oldest first. `[0]` is the oldest retained scan — the release-time (`integration="code"`) scan when history is enabled from the first scan. Absent unless `scan_history_size > 0` |
| `.sca.rescan_count` | number | *(opt-in)* Monotonic tally of completed re-scans, used to enforce `max_rescans` independently of the (capped) `.sca.history[]` length. Present when scan history or `max_rescans` is enabled |
| `.sca.native.trivy.cicd` | object | CI command detection data (command, version) |
| `.container_scan.source` | object | Source metadata for the container image scan (tool, version, integration) |
| `.container_scan.image` | string | The scanned image reference (e.g. `registry/app:tag`) |
| `.container_scan.vulnerabilities` | object | Severity counts for the image scan (critical, high, medium, low, total) |
| `.container_scan.findings[]` | array | Individual image findings (OS and application packages) |
| `.container_scan.os` | object | Detected base-image OS family and version |
| `.container_scan.summary` | object | Summary booleans (has_critical, has_high, all_fixable) |
| `.container_scan.native.trivy` | object | Raw Trivy results for the image scan |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `auto` | code | Auto-scans the repository filesystem for dependency vulnerabilities → `.sca` |
| `cicd` | ci-after-command | Detects Trivy executions in CI; routes image scans (`trivy image <ref>`) to `.container_scan` and filesystem scans (`trivy fs`) to `.sca` |
| `rescan` | cron | Re-runs the `auto` scan on a schedule (daily by default) and overwrites `.sca` so the SCA policy re-evaluates against newly-published CVEs; optionally snapshots prior scans into `.sca.history[]` (opt-in via `scan_history_size` — see [Scan history](#scan-history-point-in-time-audit)) |
| `container-scan` | after-json | Automatically scans the image the docker collector records as **pushed** (`.containers.native.docker.cicd.cmds[]`), as soon as it's published — resolves it, pulls it, scans it, writes `.container_scan` |
| `container-rescan` | cron | Re-scans the most recently **pushed** image on a schedule, so an already-shipped image is re-checked against CVEs disclosed since it was built |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
```

Zero configuration required. Works with any language Trivy supports.

By default this also enables the `rescan` cron sub-collector, which re-runs the
scan daily on each component's default branch and overwrites `.sca`. To keep the
on-push (`auto`) and CI-detection (`cicd`) scans but turn the scheduled re-scan
off, exclude it:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
    exclude: [rescan]
```

### Scan history (point-in-time audit)

By default the `rescan` cron **overwrites** `.sca` each run — the SCA policy
always sees the latest scan and the previous result is discarded. Because an
**unchanged** artifact accrues newly-disclosed CVEs over time, you may want to
keep each scan as a point-in-time record (e.g. "here's what the scan looked
like when we shipped this release"). Opt in by keeping a bounded history:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
    with:
      scan_history_size: "30"   # keep up to 30 prior scans in .sca.history[]
      max_rescans: "0"          # 0 = keep re-scanning forever (default)
```

With `scan_history_size > 0`, each re-scan snapshots the current `.sca`
(source + counts + summary, including the `collected_at` timestamp) into
`.sca.history[]` **before** overwriting `.sca`:

- `.sca` (unchanged) — the **current** scan the SCA policy evaluates.
- `.sca.history[0]` — the **oldest retained** scan, preserved even once the cap
  is reached. When history is enabled from the component's first scan (the
  intended setup) this is the **release-time** scan; each entry carries its own
  `source` (`integration` + `collected_at`), so the release-time scan is the
  `integration: "code"` entry — not an assumption about position.
- `.sca.history[1..]` — successive prior re-scans, oldest first.

> **Enabling history on an already-scanned component:** if a component has
> already been re-scanning (overwriting `.sca`) before you turn on
> `scan_history_size`, its release-time scan is already gone, so `.sca.history[0]`
> will be the current `.sca` at enable time (an `integration: "cron"` entry), not
> the original `code` scan. For guaranteed release-time capture, enable history
> from the component's first scan.

The SCA policy never reads `.sca.history`, so enabling this changes nothing for
policy evaluation — `.sca` behaves identically whether history is on or off.

| Input | Default | Effect |
|-------|---------|--------|
| `scan_history_size` | `0` | Max entries kept in `.sca.history[]`. `0` disables history (today's overwrite-only behavior). At the cap the oldest entry (`[0]`) is kept and the second-oldest is dropped. |
| `max_rescans` | `0` | Stop re-scanning a component after this many re-scans (`0` = unlimited). Counted independently via `.sca.rescan_count`, so it stands alone — no dependency on `scan_history_size`. |

Both default to off, so existing installs are unchanged. Only the `rescan` cron
maintains history — the on-push `auto` scan ignores these inputs.

**Container image scanning.** Beyond source dependencies, this collector scans **built container images** and writes results to the normalized `.container_scan` path, consumed by the [`container-scan`](../../policies/container-scan) policy. Three sub-collectors feed it, none of which installs Trivy in your pipeline:

- **`cicd`** *(detect)* — if your pipeline already runs `trivy image <ref>` itself, that scan is captured to `.container_scan` automatically. A `trivy fs` scan still routes to `.sca`. No install, no extra config.
- **`container-scan`** *(on-push)* — automatically scans the image the moment it's published. Hooks `after-json` on `.containers.native.docker.cicd.cmds`, so when the docker collector records a pushed image, Lunar resolves it, pulls it, and scans it — no schedule lag.
- **`container-rescan`** *(scheduled re-scan)* — a daily cron that re-scans that shipped image on a tick, catching CVEs **disclosed after it was built**. Resolves from *pushes* (`.containers.native.docker.cicd.cmds[]`), not `.containers.builds[]`, so a built-but-never-pushed image isn't scanned.

All three scan the shipped image *itself* in the Trivy collector image — no install in your CI. (No push recorded → nothing to scan; the sub-collector skips. Use the `container_image` input to pin an image explicitly.) Enable the [`docker`](../docker) collector alongside this one so its CI `docker push` commands are recorded:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/docker@main
    on: ["domain:your-domain"]
  - uses: github://earthly/lunar-lib/collectors/trivy@main
    on: ["domain:your-domain"]
```

> **On-push scanning requires a Hub with the `after-json` collector hook.** The `cicd` and `container-rescan` sub-collectors work on any Hub; `container-scan` needs the `after-json` hook. On a Hub without it, keep the scheduled `container-rescan` for image coverage and `exclude: [container-scan]`.

**Private registries:** the `container-rescan` cron pulls the image, so a private registry needs the `REGISTRY_USERNAME` (or `REGISTRY_USER`) / `REGISTRY_PASSWORD` secrets. Trivy's vulnerability database is a modest download at scan time.

> **Note:** If you already use the `snyk` collector, the `trivy` collector will overwrite `.sca` data since both write to the same paths. Use one SCA scanner per component, not both.
