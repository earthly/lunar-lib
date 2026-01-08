# README Collector

Collects README file information including existence, line count, and section headings.

## Overview

This collector scans the repository root for a README file and extracts metadata about its contents. It checks if the file exists, counts the number of lines, and extracts section headings (headers starting with `#`). The collector runs on code changes and provides data for documentation-related policies.

By default, the collector checks for README files in the following order (first match wins):
1. `README.md` (Markdown)
2. `README` (no extension)
3. `README.txt` (plain text)
4. `README.rst` (reStructuredText)

This can be customized via the `filenames` input.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.repo.readme.exists` | boolean | Whether a README file exists in the repository root |
| `.repo.readme.lines` | number | Number of lines in the README file (only present if file exists) |
| `.repo.readme.sections[]` | array | List of section headings extracted from the README file (only present if file exists) |

See the example below for the full structure.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "repo": {
    "readme": {
      "exists": true,
      "lines": 150,
      "sections": [
        "Installation",
        "Usage",
        "API",
        "Contributing",
        "License"
      ]
    }
  }
}
```

When README file doesn't exist:

```json
{
  "repo": {
    "readme": {
      "exists": false
    }
  }
}
```

</details>

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `filenames` | No | `README.md,README,README.txt,README.rst` | Comma-separated list of README filenames to check (first match wins). Relative paths are supported (e.g., `doc/README.md`, `docs/README.md`). |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/readme@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:
    #   filenames: "README.md,docs/README.md"  # Customize which files to check
```

## Related Policies

This collector is typically used with:
- [`readme`](https://github.com/earthly/lunar-lib/tree/main/policies/readme) - README best practices policies

