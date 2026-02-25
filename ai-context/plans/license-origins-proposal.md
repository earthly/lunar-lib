# License Origins Collector — Proposal

**Status:** RFC — seeking feedback before implementation
**PR:** [earthly/lunar-lib#70](https://github.com/earthly/lunar-lib/pull/70)

---

## Problem

In regulated industries, auditors review software dependencies for geographic origin signals — country names in license files, copyright holder addresses, governing law clauses. This is currently a fully manual process.

**Real-world example:** A project was delayed because an auditor found a dependency whose `LICENSE` file contained a German address in the copyright holder line (`"Copyright 2024 Hans Mueller, Berlin, Germany"`). The team had no automated way to detect this before the audit flagged it.

We want to automate this scan so teams can review flagged packages *before* an external audit catches them.

---

## Proposed Approach

A `license-origins` code-hook collector that:

1. **Generates an SBOM** (or reads one from Component JSON — see [Gotcha: Collector Dependencies](#gotcha-collector-dependencies))
2. **For each dependency**, checks a **configurable Postgres cache** for prior results
3. **On cache miss**, scans the dependency's license files for country name mentions
4. **Caches the result** in Postgres keyed by PURL@version (immutable — never invalidates)
5. **Writes structured results** to `.sbom.license_origins` in Component JSON

### Architecture

```
Collector runs on code push
  │
  ├── Generate SBOM (syft) → get dependency PURLs
  │
  ├── Connect to configured Postgres (if cache enabled)
  │     CREATE TABLE IF NOT EXISTS license_origin_cache (...)
  │
  ├── For each PURL:
  │     ├── Cache HIT  → use cached countries/excerpts
  │     └── Cache MISS → find LICENSE/COPYING/NOTICE in dep directory
  │                       grep for ~200 country names
  │                       INSERT into cache
  │
  └── Write .sbom.license_origins to Component JSON
```

### Cache Storage: Configurable Backend

The cache backend is configurable via collector inputs — the collector doesn't know or care what database it's talking to:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/license-origins@main
    on: ["domain:engineering"]
    with:
      # Point at the hub's own Postgres (most common — zero new infra)
      cache_db_host: "postgres"
      cache_db_port: "5432"
      cache_db_name: "hub"
      cache_db_user: "license_cache_user"
      cache_db_password: "somepassword"

      # Or point at a separate database
      # cache_db_host: "my-rds-instance.amazonaws.com"

      # Or disable caching entirely — scan fresh every time
      # cache_enabled: "false"
```

**Most common setup:** Point at the hub's own Postgres. Just create a DB user with CREATE TABLE + INSERT + SELECT privileges on a schema. The collector auto-creates the `license_origin_cache` table on first run (idempotent). No hub migrations needed, no platform changes.

**Cache table schema:**

```sql
CREATE TABLE IF NOT EXISTS license_origin_cache (
    purl        TEXT PRIMARY KEY,          -- pkg:npm/lodash@4.17.21
    countries   TEXT[],                    -- {Germany,Netherlands}
    excerpts    JSONB,                     -- [{"country":"Germany","line":"Copyright 2024 Hans, Berlin, Germany"}]
    source      TEXT DEFAULT 'local',      -- 'local' or 'clearlydefined'
    scanned_at  TIMESTAMPTZ DEFAULT NOW()
);
```

**Why this is cacheable forever:** `lodash@4.17.21`'s license text will never change. Once scanned, the result is permanent for that PURL@version. The database only grows, never needs invalidation.

**Cache warm-up:** For a typical project with ~200 dependencies, the first scan is slow (scanning each license file). But since most packages are shared across projects (lodash, express, react, etc.), the cache warms up fast across components. After a few projects, the cache hit rate would be 95%+.

### Future: Cloud-Hosted Lookup Service

If there's demand from multiple users for this plugin, the cache database could be promoted to a cloud-hosted service — a lightweight SaaS that provides PURL → country-of-origin lookups. Instead of each customer maintaining their own cache, they'd query a shared, pre-warmed database with millions of pre-scanned packages and 99%+ cache hit rates.

But that's a future evolution. The local Postgres approach works today with zero new infrastructure.

---

## Gotcha: Collector Dependencies

**Current limitation:** Lunar doesn't support collector dependency ordering yet. This collector needs a list of dependencies (PURLs) to know what to scan. Ideally it would read from:

- `.sbom.auto.cyclonedx.components[].purl` (written by the `syft` collector)
- `.lang.<name>.dependencies[]` (written by language collectors)

But since we can't guarantee those run first, **v1 of this collector must generate its own SBOM internally** — it will bundle syft and run it as a first step to get the dependency list. This means:

1. The Docker image needs syft bundled (adds ~50MB)
2. There's redundant work if the syft collector also runs on the same component
3. The collector is heavier than it needs to be

**Near-term fix:** When collector dependencies land as a platform feature, this collector should declare:

```yaml
collectors:
  - name: scan
    depends_on:
      - collector: syft
        sub_collector: generate
```

Then it reads PURLs directly from Component JSON instead of re-generating the SBOM. The syft bundling and internal generation step gets removed, making the collector much lighter.

**Alternative for v1:** If the user already has syft configured and the SBOM exists in Component JSON, the collector could try reading it first and only fall back to generating its own if no SBOM data is found. This is a reasonable middle ground.

---

## Component JSON Schema

### Output Path: `.sbom.license_origins`

```json
{
  "sbom": {
    "license_origins": {
      "source": {
        "tool": "license-origins",
        "integration": "code",
        "version": "0.1.0"
      },
      "packages": [
        {
          "purl": "pkg:npm/scheduler-lib@2.1.0",
          "name": "scheduler-lib",
          "license_file": "node_modules/scheduler-lib/LICENSE",
          "countries": ["Germany"],
          "excerpts": [
            "Copyright 2024 Hans Mueller, Berlin, Germany"
          ],
          "cached": false
        },
        {
          "purl": "pkg:npm/date-utils@1.0.3",
          "name": "date-utils",
          "license_file": "node_modules/date-utils/LICENSE",
          "countries": ["Netherlands"],
          "excerpts": [
            "Licensed under the laws of the Netherlands"
          ],
          "cached": true
        }
      ],
      "summary": {
        "files_scanned": 185,
        "packages_with_mentions": 2,
        "countries_found": ["Germany", "Netherlands"],
        "cache_hits": 140,
        "cache_misses": 45
      }
    }
  }
}
```

### Policy Usage

Pair with a proposed `blocked-origins` sub-policy on the existing SBOM policy:

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

---

## Investigation: Existing Third-Party Services

We evaluated whether existing services already solve this problem. **None do exactly what we need**, but some provide partial data:

### deps.dev (Google Open Source Insights)

- **API:** `https://api.deps.dev/v3/systems/{ecosystem}/packages/{name}/versions/{version}`
- **What it returns:** SPDX license ID (e.g., `"MIT"`), source repo links, advisory keys
- **What it does NOT return:** License text, copyright holders, author addresses, country info
- **Verdict:** ❌ Useless for our use case. Just gives `"MIT"` — the same data syft already captures. No text to grep.

### ClearlyDefined (Open Source Initiative)

- **API:** `https://api.clearlydefined.io/definitions/{type}/{provider}/{namespace}/{name}/{version}`
- **What it returns:** Copyright holder strings extracted from license files via scancode/licensee:
  ```json
  {
    "attribution": {
      "parties": [
        "Copyright Kenneth Reitz",
        "Copyright 2019 Kenneth Reitz"
      ]
    }
  }
  ```
- **What it does NOT return:** Full license text body. Only copyright lines.
- **Verdict:** ⚠️ Gets ~70% of the way. Copyright lines are where country names most commonly appear (addresses), but misses "governing law" clauses and other in-body mentions. Coverage is inconsistent — some packages have zero attribution parties despite having license files.

### Package Registries Directly (npm, PyPI, Maven)

- **npm:** Returns `author.name`, `author.email`, `maintainers[].email`. Email domains (`.de`, `.ru`) are weak signals — most use gmail.
- **PyPI:** Returns `author`, `author_email`. Same weak-signal problem.
- **Maven Central:** POM files have `<developers>` and `<organization>` but no country field.
- **Verdict:** ❌ Too noisy, too incomplete. Author names and email domains are unreliable country indicators.

### Socket.dev / Sonatype / Snyk

- Commercial supply chain intelligence services with curated provenance databases.
- Likely have the best data but require paid subscriptions and API keys.
- **Verdict:** Worth exploring for enterprise tier in the future, but adds vendor dependency and cost.

### Conclusion

**No existing service does "grep license text for country names."** ClearlyDefined is the closest with copyright party extraction. Our collector would be novel in this space.

A hybrid approach is possible for the future: query ClearlyDefined as a first-pass enrichment (free, cached on their side), then fall back to local scanning for packages where their data is incomplete. The results from either source get cached in our Postgres table.

---

## Known Limitations & False Positives

### False Positive Risk

Country names that are also common English words:

| Country | Risk | Example |
|---------|------|---------|
| Georgia | High | US state, person's name |
| Jordan | High | Person's name |
| Turkey | Medium | The bird |
| Chad | Medium | Person's name |
| China | Low-Medium | "fine china" (rare in license text) |

**Mitigation:** Excerpts (matching lines) are included so reviewers can quickly dismiss false positives. Recommended workflow is detection + human review, not auto-blocking. Start with `enforcement: warn`.

### What This Does NOT Detect

- Packages developed in a country whose license text doesn't mention it (most common gap — MIT template with just a name, no address)
- Transitive maintainer origins (the actual humans behind the code)
- Runtime dependencies that phone home to specific jurisdictions
- Packages where the license file was copied from a template

### Recommended Pairing

For broader coverage, combine with:
- `disallowed-packages` policy check (regex on package names/groups/PURLs — catches `ru.yandex.*`, `com.alibaba.*`)
- ClearlyDefined enrichment as a secondary data source (future)

---

## Open Questions

1. **Should the collector bundle syft or assume the SBOM already exists?** (See [Gotcha](#gotcha-collector-dependencies).) Bundling syft is self-contained but heavy. Reading from Component JSON is lighter but requires collector dependency ordering.

2. **Should we query ClearlyDefined as a secondary enrichment source** in addition to local scanning? It would add coverage for the copyright-line case but introduces an external API dependency.

3. **Country list scope:** ISO country names only, or include common variants (`Deutschland`, `PRC`, `ROC`, city names like `Beijing`, `Moscow`)?

4. **Should the `blocked-origins` policy be a sub-policy under `sbom`, or its own standalone policy?**

5. **DB user provisioning:** Should the collector docs include a one-liner for creating the cache user on the hub Postgres, or should we add it as an optional hub migration?
