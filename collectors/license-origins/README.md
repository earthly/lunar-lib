# License Origins Collector

Generate SBOMs and scan dependency license files for country-of-origin mentions.

## Overview

This collector generates a CycloneDX SBOM using syft, fetches dependencies per language ecosystem (Rust, Go, Node.js, Python), and scans each dependency's license files for country-of-origin mentions. Results are cached in Postgres keyed by PURL@version. Replaces the `syft` collector — use it *instead of* `syft` on the same component.

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
