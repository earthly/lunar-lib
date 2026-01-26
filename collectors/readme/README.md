# `readme` Collector

Collects README file information including existence, line count, and section headings.

## Overview

This collector scans the repository root for a README file and extracts metadata about its contents, including existence, line count, and section headings. It runs on code changes and checks for common README variants (`README.md`, `README`, `README.txt`, `README.rst`) in order, which can be customized via the `path` input.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.repo.readme.exists` | boolean | Whether a README file exists in the repository root |
| `.repo.readme.path` | string | The path of the README file found (only present if file exists) |
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
      "path": "README.md",
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
| `path` | No | `README.md,README,README.txt,README.rst` | Comma-separated list of README paths to check (first match wins) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/readme@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:
    #   path: "README.md,docs/README.md"  # Customize which files to check
```

## Related Policies

This collector is typically used with:
- [`readme`](https://github.com/earthly/lunar-lib/tree/main/policies/readme) - README best practices policies

