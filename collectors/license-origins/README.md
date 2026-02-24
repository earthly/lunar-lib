# License Origin Scanner

Scans dependency license files for geographic origin mentions (country names, jurisdictions).

## Overview

This collector walks dependency directories and scans `LICENSE`, `COPYING`, and `NOTICE` files for mentions of country names. It produces a structured report of which packages reference which countries in their license text, giving compliance teams visibility into supply chain provenance.

**Status: Experimental / RFC** — This is a proposal. See [Design Considerations](#design-considerations) for tradeoffs.

## Motivation

In regulated industries, auditors review the geographic origins of software dependencies for sanctions compliance (OFAC, EU), export control (EAR/ITAR), or internal supply chain policy. Today this is a manual process: auditors grep through license files and flag packages that mention certain countries.

A real-world example: a project was delayed because an auditor found a dependency whose LICENSE file referenced Germany in the copyright holder's address. The team had no automated way to detect this before the audit.

This collector automates that initial scan so teams can review flagged packages *before* an auditor does.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sbom.license_origins.source` | object | Collector metadata (tool, version) |
| `.sbom.license_origins.packages[]` | array | Packages with country mentions |
| `.sbom.license_origins.packages[].name` | string | Package name |
| `.sbom.license_origins.packages[].version` | string | Package version (if detectable) |
| `.sbom.license_origins.packages[].license_file` | string | Relative path to the license file |
| `.sbom.license_origins.packages[].countries[]` | array | Country names found in the file |
| `.sbom.license_origins.packages[].excerpts[]` | array | Lines containing the country mentions (context) |
| `.sbom.license_origins.summary` | object | Scan summary |
| `.sbom.license_origins.summary.files_scanned` | int | Total license files found |
| `.sbom.license_origins.summary.packages_with_mentions` | int | Number of packages with country mentions |
| `.sbom.license_origins.summary.countries_found[]` | array | Deduplicated list of all countries detected |

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
```

### Policy Usage

Pair with the SBOM policy's `blocked-origins` check (proposed):

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sbom@main
    on: ["domain:engineering"]
    enforcement: block-pr
    include: [blocked-origins]
    with:
      blocked_countries: "Russia,China,Iran,North Korea"
      # Or use an allowlist (stricter):
      # allowed_countries: "United States,Canada,United Kingdom,Germany,France"
```

## How It Works

1. Detect dependency directories present in the repo:
   - `node_modules/` (npm/yarn)
   - `vendor/` (Go, PHP)
   - Python: `venv/`, `.venv/`, `site-packages/` (if present)
   - Java: `.gradle/`, `.m2/` (if present)
2. Find all files matching `LICENSE*`, `COPYING*`, `NOTICE*` (case-insensitive) within those directories.
3. Grep each file against a list of ~200 country names.
4. For matches, extract the matching line as context (the "excerpt").
5. Derive the package name from the directory path (e.g., `node_modules/<pkg>/LICENSE` → `<pkg>`).
6. Write structured results to `.sbom.license_origins`.

## Examples

### Component JSON — Packages with country mentions

```json
{
  "sbom": {
    "license_origins": {
      "source": { "tool": "license-origins", "integration": "code", "version": "0.1.0" },
      "packages": [
        {
          "name": "scheduler-lib",
          "version": "2.1.0",
          "license_file": "node_modules/scheduler-lib/LICENSE",
          "countries": ["Germany"],
          "excerpts": ["Copyright 2024 Hans Mueller, Berlin, Germany"]
        }
      ],
      "summary": {
        "files_scanned": 185,
        "packages_with_mentions": 1,
        "countries_found": ["Germany"]
      }
    }
  }
}
```

### Component JSON — No mentions found (clean)

```json
{
  "sbom": {
    "license_origins": {
      "source": { "tool": "license-origins", "integration": "code", "version": "0.1.0" },
      "packages": [],
      "summary": {
        "files_scanned": 142,
        "packages_with_mentions": 0,
        "countries_found": []
      }
    }
  }
}
```

---

## Design Considerations

### Why scan license text instead of using registry metadata?

We evaluated several approaches to detect the geographic origin of dependencies:

| Approach | Accuracy | Coverage | Complexity | Notes |
|----------|----------|----------|------------|-------|
| **License text scan** (this) | ⚠️ Medium | Good — works for any ecosystem | Low | False positives (see below) |
| Package namespace regex | ✅ High | Low — only catches `ru.yandex.*`, `com.alibaba.*` etc. | Low | Misses packages with neutral names |
| Registry metadata enrichment | ⚠️ Medium | ~40-50% | High | Author emails, homepages — self-reported, often blank |
| GitHub API org location | ⚠️ Medium | ~50% (GitHub-hosted only) | Medium | Self-reported, optional field |
| Commercial supply chain DB | ✅ High | ~90%+ | Medium | Requires paid API (Socket.dev, Sonatype) |

We chose license text scanning because:
- It matches exactly what an auditor does manually
- Works across all ecosystems without API calls
- No external dependencies or API keys
- The data (license files) is already on disk during collection

### Known False Positives

Country names that are also common English words or proper names:

| Country | False Positive Risk | Example |
|---------|-------------------|---------|
| Georgia | High | US state, person's name |
| Jordan | High | Person's name |
| Turkey | Medium | The bird |
| Chad | Medium | Person's name |
| China | Low-Medium | "fine china" (rare in license text) |
| Monaco | Low | Could be a brand name |
| Guinea | Low | "guinea pig" (rare in license text) |

**Mitigation:** The collector provides excerpts (the matching line) so reviewers can quickly dismiss false positives. The recommended workflow is detection + human review, not auto-blocking.

### Recommended Usage Pattern

This collector is best used as a **reporting/detection tool** rather than an auto-blocker:

1. Run the collector across all components
2. Review `license_origins.summary.countries_found` in dashboards
3. Investigate flagged packages before external audits
4. Use the SBOM policy's `blocked-origins` check with `enforcement: warn` initially
5. Graduate to `enforcement: block-pr` only after tuning the country list and reviewing false positives

### What this does NOT detect

- Packages developed in a country but whose license text doesn't mention it
- Transitive maintainer origins (the actual humans behind the code)
- Runtime dependencies that phone home to specific jurisdictions
- Packages where the license file was copied from a template (e.g., MIT license with no address)

For higher coverage, combine with the `disallowed-packages` policy check (regex on package names/groups/PURLs) and consider commercial supply chain intelligence tools.
