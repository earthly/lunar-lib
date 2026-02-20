# Manifest Cyber Collector

Collects SBOM management, vulnerability enrichment, and license compliance data from [Manifest Cyber](https://www.manifestcyber.com/).

## Overview

This collector integrates with Manifest Cyber's SBOM management platform to provide visibility into SBOM lifecycle, vulnerability enrichment, and license compliance. It supports two integration methods: REST API verification on each commit (with retry for processing delay) and CLI detection in CI pipelines.

Unlike raw SBOM generators (e.g., Syft), Manifest Cyber acts as the **SBOM management layer** — it ingests, enriches, and tracks SBOMs over time. This collector answers questions like "is our SBOM actively managed?" and "what does the enriched vulnerability picture look like?" that generation-only tools cannot.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.source` | object | Source metadata (tool: manifest, integration method) |
| `.sbom.summary` | object | Normalized SBOM summary (package count, licenses, freshness) |
| `.sbom.native.manifest` | object | Raw Manifest Cyber API data (asset info, SBOM format) |
| `.sbom.native.manifest.vulnerabilities` | object | Vulnerability counts from SBOM enrichment (critical/high/medium/low) |
| `.sbom.native.manifest.exploitability` | object | CISA KEV and EPSS exploitability data |
| `.sbom.cicd` | object | CI CLI detection metadata and commands |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `api` | code | Queries Manifest Cyber REST API on each commit to verify SBOM upload. Retries for up to 5 minutes to allow for processing delay. |
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

### Configuration Examples

**API collector only** (most common — verifies SBOM upload on each commit):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest@main
    on: ["domain:your-domain"]
    include: [api]
```

**All integration methods:**

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest@main
    on: ["domain:your-domain"]
```
