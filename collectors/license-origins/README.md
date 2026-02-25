# License Origin Scanner

Scans dependency license files for geographic origin mentions (country names, jurisdictions) with Postgres-backed caching.

## Overview

This collector discovers dependencies via an internal SBOM generation step, then scans their `LICENSE`, `COPYING`, and `NOTICE` files for mentions of country names. Results are cached in a configurable Postgres database so that once a package version is scanned, the result is reused instantly across all future runs and components.

**Status: Experimental / RFC** — See the [full proposal](https://github.com/earthly/earthly-agent-config/blob/main/plans/license-origins-proposal.md) for design rationale, alternatives explored, and open questions.

## Motivation

In regulated industries, auditors review the geographic origins of software dependencies for sanctions compliance (OFAC, EU), export control (EAR/ITAR), or internal supply chain policy. Today this is a manual process: auditors grep through license files and flag packages that mention certain countries.

This collector automates that scan so teams can review flagged packages *before* an auditor does.

## Collected Data

| Path | Type | Description |
|------|------|-------------|
| `.sbom.license_origins.source` | object | Collector metadata (tool, version) |
| `.sbom.license_origins.packages[]` | array | Packages with country mentions |
| `.sbom.license_origins.packages[].purl` | string | Package URL |
| `.sbom.license_origins.packages[].name` | string | Package name |
| `.sbom.license_origins.packages[].license_file` | string | Relative path to the license file |
| `.sbom.license_origins.packages[].countries[]` | array | Country names found in the file |
| `.sbom.license_origins.packages[].excerpts[]` | array | Lines containing the country mentions (context) |
| `.sbom.license_origins.packages[].cached` | bool | Whether this result came from the cache |
| `.sbom.license_origins.summary.files_scanned` | int | Total license files found |
| `.sbom.license_origins.summary.packages_with_mentions` | int | Packages with country mentions |
| `.sbom.license_origins.summary.countries_found[]` | array | Deduplicated list of all countries detected |
| `.sbom.license_origins.summary.cache_hits` | int | Results served from cache |
| `.sbom.license_origins.summary.cache_misses` | int | Results from fresh scans |

## Collectors

| Collector | Description |
|-----------|-------------|
| `scan` | Scans license files in dependency directories for country mentions (code hook) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    with:
      # Point at the hub's own Postgres (zero new infra)
      cache_db_host: "postgres"
      cache_db_port: "5432"
      cache_db_name: "hub"
      cache_db_user: "license_cache_user"
      cache_db_password: "somepassword"
```

### Cache Database Setup

The collector auto-creates its table on first run. You just need a Postgres user with appropriate privileges:

```sql
-- Run once on the target Postgres (e.g., the hub database)
CREATE USER license_cache_user WITH PASSWORD 'somepassword';
GRANT CREATE ON DATABASE hub TO license_cache_user;
-- The collector runs CREATE TABLE IF NOT EXISTS on first use
```

### Without Caching

Omit the `cache_db_*` inputs to disable caching. The collector will scan every dependency fresh each run:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    # No cache_db_* inputs — scans fresh every time
```

### Policy Usage

Pair with the SBOM policy's `blocked-origins` check (proposed):

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sbom@main
    enforcement: warn          # Start with warn — review false positives first
    include: [blocked-origins]
    with:
      blocked_countries: "Russia,China,Iran,North Korea"
      # Or allowlist mode (stricter):
      # allowed_countries: "United States,Canada,United Kingdom,Germany,France"
```

## How It Works

1. **Discover dependencies:** Run bundled syft to generate a CycloneDX SBOM and extract PURLs.
2. **Check cache:** For each PURL, query the configured Postgres cache. Cache hits skip scanning.
3. **Scan license files:** For cache misses, locate the dependency's directory and find `LICENSE*`, `COPYING*`, `NOTICE*` files. Grep each against ~200 country names.
4. **Store results:** Insert scan results into the cache (keyed by PURL — immutable, never invalidates).
5. **Write output:** Aggregate all results (cached + fresh) and write to `.sbom.license_origins`.

### Why Caching Works

Package versions are immutable: `lodash@4.17.21`'s license text will never change. Once scanned, the result is permanent. The cache only grows, never needs invalidation. After scanning a few components, shared dependencies (lodash, express, react, etc.) are already cached, giving 95%+ hit rates.

## Gotcha: Collector Dependencies

**Current limitation:** Lunar doesn't yet support collector dependency ordering. This collector needs a list of dependencies (PURLs) to know what to scan. Ideally it would read from Component JSON paths already written by other collectors:

- `.sbom.auto.cyclonedx.components[].purl` (from the `syft` collector)
- `.lang.<name>.dependencies[]` (from language collectors)

Since we can't guarantee those run first, **v1 bundles syft internally** and generates its own SBOM as a first step. This means:

- The Docker image is larger (~50MB for syft)
- There's redundant work if the syft collector also runs on the same component
- The collector is heavier than it needs to be

**When collector dependencies land** as a platform feature, this collector should declare a dependency on `syft.generate` and read PURLs directly from Component JSON, eliminating the bundled syft and redundant SBOM generation.

## Examples

### Component JSON — Packages with country mentions

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

### Component JSON — Clean scan (no mentions)

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

## Known Limitations

### False Positives

Country names that are also common English words:

| Country | Risk | Example |
|---------|------|---------|
| Georgia | High | US state, person's name |
| Jordan | High | Person's name |
| Turkey | Medium | The bird |
| Chad | Medium | Person's name |
| China | Low-Medium | "fine china" (rare in license text) |

Excerpts (matching lines) are included so reviewers can quickly dismiss false positives. **Recommended workflow:** Start with `enforcement: warn` and human review before graduating to `block-pr`.

### What This Does NOT Detect

- Packages developed in a country whose license text doesn't mention it
- Transitive maintainer origins (the actual humans behind the code)
- Runtime dependencies that phone home to specific jurisdictions
- Packages where the license file was copied from a template (MIT with just a name, no address)

### Third-Party Services Explored

We investigated existing services. None solve this problem completely:

- **deps.dev (Google):** Returns SPDX license IDs only (`"MIT"`), not text. Useless for country detection.
- **ClearlyDefined:** Returns copyright holder strings extracted via scancode — gets ~70% of cases where countries appear in copyright lines, but misses "governing law" clauses and body text.
- **Package registries (npm, PyPI):** Author names/emails are weak signals — most use gmail.com.
- **Commercial (Socket.dev, Sonatype):** Best data but paid, adds vendor dependency.

See the [full proposal](https://github.com/earthly/earthly-agent-config/blob/main/plans/license-origins-proposal.md) for the detailed investigation.
