# Collector README Template

Use this template when creating the `README.md` for a new collector plugin.

---

# `{directory-name}` Collector

{One-line description of what this collector does}

## Overview

{2-3 sentences explaining what data this collector gathers, when it runs, and why it's useful.}

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.example.items[]` | array | List of Y found in the repository |
| `.example.native.{tool}` | object | Raw tool output for advanced policy use |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `example-collector-1` | Checks for the existence of X |
| `example-collector-2` | Adds more data about Y |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/{path-to-collector}@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:                     # Uncomment if inputs are needed
    #   threshold: "20"
```

---

## Template Usage Notes

When using this template:

1. Replace all `{placeholders}` with actual values
2. Only list top-level paths in the table (e.g., `.example.items[]`, `.example.summary`)
3. Remove this "Template Usage Notes" section from the final README
