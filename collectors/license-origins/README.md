# License Origins Collector

Scan dependency license files for country-of-origin mentions.

## Overview

This collector fetches dependencies per language ecosystem (Rust, Go, Node.js, Python), generates an internal SBOM to enumerate them, then scans each dependency's license files for country-of-origin mentions. Results are cached in Postgres keyed by PURL@version. Use alongside the `syft` collector for full SBOM + origin coverage. When collector dependency features are available, this will run after the syft collector instead of generating its own SBOM.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.license_origins.source` | object | License origins source metadata |
| `.sbom.license_origins.packages[]` | array | Packages with country mentions (purl, countries, excerpts) |
| `.sbom.license_origins.summary` | object | Scan statistics (files scanned, cache hits/misses, countries found) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `scan` | Scans dependency license files for country name mentions (code hook) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
```

To disable caching (scan fresh every time):

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    with:
      cache_enabled: "false"
```

Optional secrets (for Postgres caching):
- `CACHE_DB_PASSWORD` — Postgres password for the cache database. If not set, caching is disabled and every scan runs fresh. The connection defaults (`postgres:5432/hub`, user `lunar`) match the standard Lunar hub database. Override with `cache_db_host`, `cache_db_port`, `cache_db_name`, `cache_db_user` inputs if needed.
