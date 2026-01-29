# Cataloger README Template

Use this template when creating the `README.md` for a new cataloger plugin.

---

# `{directory-name}` Cataloger

{One-line description of what this cataloger does}

## Overview

{2-3 sentences explaining what catalog data this cataloger syncs, from which source, and why it's useful.}

## Synced Data

This cataloger writes to the following Catalog JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.components[*].owner` | string | Component owner email from {source} |
| `.components[*].domain` | string | Domain assignment from {source} |
| `.components[*].tags[]` | array | Tags inferred from {source} |
| `.domains[*].description` | string | Domain description from {source} |
| `.domains[*].owner` | string | Domain owner email from {source} |

{Adjust the table above to list only the specific fields your cataloger writes. Remove paths that don't apply.}

## Catalogers

This plugin provides the following catalogers (use `include` to select a subset):

| Cataloger | Description |
|-----------|-------------|
| `sync-components` | Syncs component definitions from {source} |
| `sync-domains` | Syncs domain hierarchy from {source} |

## Hook Type

| Hook | Schedule/Trigger | Description |
|------|------------------|-------------|
| `cron` | `0 2 * * *` | Runs daily at 2am UTC |

Or for repo-based catalogers:

| Hook | Trigger | Description |
|------|---------|-------------|
| `repo` | `github.com/acme/catalog` | Runs on commits to the catalog repo |

## Installation

Add to your `lunar-config.yml`:

```yaml
catalogers:
  - uses: github.com/earthly/lunar-lib/catalogers/{path-to-cataloger}@v1.0.0
    with:
      org_name: "your-org"
```

## Source System

{Brief description of the external system this cataloger syncs from, including any setup requirements on that system (e.g., API permissions, webhook configuration).}

---

## Template Usage Notes

When using this template:

1. Replace all `{placeholders}` with actual values
2. Document only the relevant paths (`.components`, `.domains`, or both)
3. Include the hook type/schedule that the cataloger uses
4. Remove this "Template Usage Notes" section from the final README
