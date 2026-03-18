# License Origins Collector

Generate SBOMs and scan dependency license files for country-of-origin mentions.

## Overview

This collector generates a CycloneDX SBOM using syft, then fetches dependencies per language ecosystem so their license files are available on disk, and scans each license file (LICENSE, COPYING, NOTICE) for geographic origin signals — country names in copyright holder lines, governing law clauses, and author addresses. It greps each license file against ~200 country names. Scan results are optionally cached in Postgres keyed by PURL@version (immutable, never invalidates), so repeated scans across projects are fast.

**Note:** This collector fully replaces the `syft` collector — use it *instead of* `syft` on the same component. In the future, when collector dependency ordering is supported, the SBOM generation will move back to the `syft` collector and this collector will depend on it.

Dependencies are fetched per language: Rust (`cargo fetch`), Go (`go mod download`), Node.js (`npm install`), and Python (`pip install`). Java is not supported in v1. The Docker image includes all supported language runtimes; if a tool is not available, that language is skipped gracefully.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.auto.source` | object | Syft source metadata (tool, integration, version) |
| `.sbom.auto.cyclonedx` | object | Full CycloneDX SBOM from syft |
| `.sbom.license_origins.source` | object | License origins source metadata |
| `.sbom.license_origins.packages[]` | array | Packages with country mentions (purl, countries, excerpts) |
| `.sbom.license_origins.summary` | object | Scan statistics (files scanned, cache hits/misses, countries found) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `scan` | Scans dependency license files for country name mentions (code hook) |

## Installation

Add to your `lunar-config.yml`. The defaults match the standard Lunar hub database, so you only need to provide the password:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    secrets:
      CACHE_DB_PASSWORD: "your-db-password"
```

To use a different database, override the connection inputs:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    with:
      cache_db_host: "my-rds-instance.amazonaws.com"
      cache_db_user: "cache_user"
      cache_db_name: "mydb"
    secrets:
      CACHE_DB_PASSWORD: "your-db-password"
```

To disable caching entirely (scan fresh every time):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    with:
      cache_enabled: "false"
```

### Why Cache?

A dependency at a specific version (e.g., `lodash@4.17.21`) has an immutable license file. Once scanned, the result never changes. The cache warms up quickly across projects since most packages are shared (lodash, express, react, etc.), reaching 95%+ hit rates after a few components.
