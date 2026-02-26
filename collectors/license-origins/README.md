# License Origin Scanner

Scans dependency license files for geographic origin mentions (country names, jurisdictions) with Postgres-backed caching.

## Overview

This collector discovers dependencies (via bundled syft), then scans their `LICENSE`, `COPYING`, and `NOTICE` files for mentions of country names. Results are cached in a configurable Postgres database keyed by PURL@version so repeat scans are instant.

**Status: Experimental**

## Collected Data

| Path | Type | Description |
|------|------|-------------|
| `.sbom.license_origins.source` | object | Collector metadata (tool, version) |
| `.sbom.license_origins.packages[]` | array | Packages with country mentions |
| `.sbom.license_origins.packages[].purl` | string | Package URL |
| `.sbom.license_origins.packages[].name` | string | Package name |
| `.sbom.license_origins.packages[].license_file` | string | Relative path to the license file |
| `.sbom.license_origins.packages[].countries[]` | array | Country names found |
| `.sbom.license_origins.packages[].excerpts[]` | array | Lines containing the mentions (context) |
| `.sbom.license_origins.packages[].cached` | bool | Whether result came from cache |
| `.sbom.license_origins.summary.files_scanned` | int | Total license files found |
| `.sbom.license_origins.summary.packages_with_mentions` | int | Packages with country mentions |
| `.sbom.license_origins.summary.countries_found[]` | array | All countries detected |
| `.sbom.license_origins.summary.cache_hits` | int | Results served from cache |
| `.sbom.license_origins.summary.cache_misses` | int | Results from fresh scans |

## Collectors

| Collector | Description |
|-----------|-------------|
| `scan` | Scans license files in dependency directories for country mentions (code hook) |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    with:
      cache_db_host: "postgres"
      cache_db_port: "5432"
      cache_db_name: "hub"
      cache_db_user: "license_cache_user"
      cache_db_password: "somepassword"
```

### Cache Database Setup

The collector auto-creates its table on first run. You just need a Postgres user:

```sql
CREATE USER license_cache_user WITH PASSWORD 'somepassword';
GRANT CREATE ON DATABASE hub TO license_cache_user;
```

### Without Caching

Omit the `cache_db_*` inputs. The collector will scan every dependency fresh each run.

### Policy Usage

Pair with the SBOM policy's `blocked-origins` check:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sbom@main
    enforcement: warn
    include: [blocked-origins]
    with:
      blocked_countries: "Russia,China,Iran,North Korea"
```

## Examples

### Packages with country mentions

```json
{
  "sbom": {
    "license_origins": {
      "source": { "tool": "license-origins", "integration": "code", "version": "0.1.0" },
      "packages": [
        {
          "purl": "pkg:npm/scheduler-lib@2.1.0",
          "name": "scheduler-lib",
          "license_file": "node_modules/scheduler-lib/LICENSE",
          "countries": ["Germany"],
          "excerpts": ["Copyright 2024 Hans Mueller, Berlin, Germany"],
          "cached": false
        }
      ],
      "summary": {
        "files_scanned": 185,
        "packages_with_mentions": 1,
        "countries_found": ["Germany"],
        "cache_hits": 140,
        "cache_misses": 45
      }
    }
  }
}
```

### Clean scan (no mentions)

```json
{
  "sbom": {
    "license_origins": {
      "source": { "tool": "license-origins", "integration": "code", "version": "0.1.0" },
      "packages": [],
      "summary": {
        "files_scanned": 142,
        "packages_with_mentions": 0,
        "countries_found": [],
        "cache_hits": 138,
        "cache_misses": 4
      }
    }
  }
}
```

## Gotcha: Collector Dependencies

Lunar doesn't yet support collector dependency ordering. This collector bundles syft internally to discover dependencies. When the platform adds `depends_on` support, this will instead read PURLs from `.sbom.auto.cyclonedx.components` written by the syft collector, eliminating the redundant SBOM generation.

## Remediation

When the `blocked-origins` policy fails:

1. Review the excerpts — dismiss false positives (e.g., "Georgia" as a US state)
2. If the origin is genuine, evaluate whether the dependency can be replaced
3. If the dependency is approved after review, add an exception or adjust the country list
