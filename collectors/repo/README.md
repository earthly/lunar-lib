# Repository Collector

Collect standard repository metadata including README, CODEOWNERS, and common configuration files.

## Overview

Aggregates repository hygiene data by scanning for README files, CODEOWNERS ownership rules, and standard configuration files. Each file type has its own subcollector that extracts rich metadata (line counts, sections, patterns) for in-depth policy checks. Consolidates the existing `readme` and `codeowners` collectors into a single top-level plugin.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.repo.readme` | object | README metadata (exists, path, lines, sections) |
| `.repo.gitignore` | object | .gitignore metadata (exists, path, lines, patterns) |
| `.repo.license` | object | LICENSE metadata (exists, path, spdx_id) |
| `.repo.security` | object | SECURITY.md metadata (exists, path, lines, sections) |
| `.repo.contributing` | object | CONTRIBUTING.md metadata (exists, path, lines, sections) |
| `.repo.editorconfig` | object | .editorconfig metadata (exists, path, sections) |
| `.ownership.codeowners` | object | Parsed CODEOWNERS data (exists, valid, owners, rules) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `readme` | Detects README files, extracts line count and section headings |
| `codeowners` | Parses CODEOWNERS file, extracts ownership rules, validates syntax |
| `gitignore` | Detects .gitignore, counts lines and active patterns |
| `license` | Detects LICENSE file, identifies SPDX license type |
| `security` | Detects SECURITY.md, extracts line count and sections |
| `contributing` | Detects CONTRIBUTING.md, extracts line count and sections |
| `editorconfig` | Detects .editorconfig, counts section blocks |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/repo@main
    on: ["domain:your-domain"]
    # with:
    #   readme_paths: "README.md,README,README.txt,README.rst"
    #   codeowners_paths: "CODEOWNERS,.github/CODEOWNERS,docs/CODEOWNERS"
```
