# Repository Collector

Collect standard repository metadata including README, CODEOWNERS, and common configuration files.

## Overview

Aggregates repository hygiene data by scanning for README files, CODEOWNERS ownership rules, and standard configuration files (.gitignore, LICENSE, SECURITY.md, CONTRIBUTING.md, .editorconfig). This collector consolidates the existing `readme` and `codeowners` collectors into a single top-level plugin, adding a `repo-files` subcollector for common file detection.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.repo.readme` | object | README file metadata (exists, path, lines, sections) |
| `.repo.files` | object | Boolean presence flags for standard repository files |
| `.ownership.codeowners` | object | Parsed CODEOWNERS data (exists, valid, owners, rules) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `readme` | Detects README files and extracts metadata (line count, section headings) |
| `codeowners` | Parses CODEOWNERS file, extracts ownership rules, validates syntax |
| `repo-files` | Scans for .gitignore, LICENSE, SECURITY.md, CONTRIBUTING.md, .editorconfig |

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
