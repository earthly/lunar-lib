# Repo Boilerplate Collector

Collect standard repository boilerplate metadata including README, CODEOWNERS, and common configuration files.

## Overview

Aggregates repository boilerplate data by scanning for README files, CODEOWNERS ownership rules, and standard configuration files. Each file type has its own subcollector that extracts rich metadata (line counts, sections, patterns) for in-depth policy checks. Consolidates the existing `readme` and `codeowners` collectors into a single top-level plugin.

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
| `.repo.changelog` | object | CHANGELOG metadata (exists, path, lines, sections) |
| `.ownership.codeowners` | object | Parsed CODEOWNERS data (exists, valid, path, scope, owners, rules) |

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
| `changelog` | Detects CHANGELOG (variants configurable), extracts line count and version sections |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/repo-boilerplate@main
    on: ["domain:your-domain"]
    # with:
    #   readme_paths: "README.md,README,README.txt,README.rst"
    #   codeowners_paths: "CODEOWNERS,.github/CODEOWNERS,docs/CODEOWNERS"
    #   codeowners_scope: "auto"   # auto | repo-root | component-dir
    #   changelog_paths: "CHANGELOG.md,CHANGELOG,CHANGES.md,HISTORY.md,RELEASES.md"
```

### Monorepos

In a monorepo, each Lunar component is a subdirectory of one git repository,
but a CODEOWNERS file is only honored by GitHub/GitLab at the repository root
(`CODEOWNERS`, `.github/CODEOWNERS`, `docs/CODEOWNERS`) — never inside a
component subdirectory. The `codeowners` collector handles this by default:
when a component's own subdirectory has no CODEOWNERS file, it falls back to
the global file at the repository root, so `.ownership.codeowners` (and every
CODEOWNERS policy) is populated for every component from that one shared file.
The `.ownership.codeowners.scope` field records whether the file was found at
the repository root (`"repo"`) or in the component's own subdirectory
(`"component"`).

The `codeowners_scope` input controls this:

| Value | Behavior |
|-------|----------|
| `auto` (default) | Check the component's own directory first, then fall back to the repository root. Correct for both single-repo and monorepo layouts. |
| `repo-root` | Only use the global CODEOWNERS at the repository root. |
| `component-dir` | Only use the component's own directory (the pre-monorepo behavior). |
