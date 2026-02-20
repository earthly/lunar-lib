# Manifest Cyber Collector

Collects SBOM management, vulnerability enrichment, and license compliance data from [Manifest Cyber](https://www.manifestcyber.com/).

## Overview

This collector integrates with Manifest Cyber's SBOM management platform to provide visibility into SBOM lifecycle, vulnerability enrichment, and license compliance. It supports three integration methods: REST API queries (cron), GitHub App status check detection (PRs), and CLI detection in CI pipelines.

Unlike raw SBOM generators (e.g., Syft), Manifest Cyber acts as the **SBOM management layer** — it ingests, enriches, and tracks SBOMs over time. This collector answers questions like "is our SBOM actively managed?" and "what does the enriched vulnerability picture look like?" that generation-only tools cannot.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.source` | object | Source metadata (tool: manifest, integration method) |
| `.sbom.summary` | object | Normalized SBOM summary (package count, licenses, freshness) |
| `.sbom.native.manifest` | object | Raw Manifest Cyber API data (vulns, exploitability, licenses) |
| `.sbom.native.manifest.github_app` | object | GitHub App status check data |
| `.sbom.cicd` | object | CI CLI detection metadata and commands |
| `.sca.source` | object | SCA source metadata from Manifest enrichment |
| `.sca.vulnerabilities` | object | Normalized vulnerability counts from enrichment |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `api` | cron (every 6h) | Queries Manifest Cyber REST API for SBOM, vulnerability, and license data |
| `github-app` | code (PRs only) | Detects Manifest Cyber GitHub App status checks on pull requests |
| `ci` | ci-after-command | Detects `manifest-cli` executions in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest@main
    on: ["domain:your-domain"]
```

### Required Secrets

| Secret | Required By | Description |
|--------|-------------|-------------|
| `MANIFEST_API_KEY` | `api` | Manifest Cyber API key ([generate in org settings](https://app.manifestcyber.com)) |
| `GH_TOKEN` | `github-app` | GitHub token for commit status API access |

### Configuration Examples

**API collector only** (most common — queries Manifest for enriched data):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest@main
    on: ["domain:your-domain"]
    include: [api]
```

**GitHub App detection only** (lightweight — just checks if Manifest App is posting status checks):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest@main
    on: ["domain:your-domain"]
    include: [github-app]
```

**All integration methods:**

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest@main
    on: ["domain:your-domain"]
```
