# Manifest Cyber Collector

Collects SBOM management, vulnerability enrichment, and license compliance data from [Manifest Cyber](https://www.manifestcyber.com/).

## Overview

This collector integrates with Manifest Cyber's SBOM management platform to provide visibility into SBOM lifecycle, vulnerability enrichment, and license compliance. It supports REST API verification on each commit (with configurable retry) and CLI detection in CI pipelines.

Unlike raw SBOM generators, Manifest Cyber acts as the **SBOM management layer** — it ingests, enriches, and tracks SBOMs over time. Note that `manifest-cli sbom` delegates to an external generator (syft by default), so the underlying generator's collector captures the raw SBOM independently.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.native.manifest_cyber` | object | Asset info (id, name, packages, format, freshness) |
| `.sbom.native.manifest_cyber.vulnerabilities` | object | Vulnerability counts from SBOM enrichment (critical/high/medium/low) |
| `.sbom.native.manifest_cyber.exploitability` | object | CISA KEV and EPSS exploitability data |
| `.sbom.native.manifest_cyber.licenses` | array | License breakdown with package counts |
| `.sbom.native.manifest_cyber.cicd.cmds` | array | CI CLI detection (command + version) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `api` | code | Verifies SBOM upload to Manifest Cyber and pulls enrichment data (vulns, licenses, exploitability). Retries with configurable attempts. |
| `cicd` | ci-after-command | Detects `manifest-cli` executions in CI pipelines |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest-cyber@main
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
  - uses: github://earthly/lunar-lib/collectors/manifest-cyber@main
    on: ["domain:your-domain"]
    include: [api]
```

**Custom retry attempts** (default: 10 attempts × 30s = ~5 min):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest-cyber@main
    on: ["domain:your-domain"]
    with:
      retry_attempts: "20"
```

**All integration methods:**

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/manifest-cyber@main
    on: ["domain:your-domain"]
```
