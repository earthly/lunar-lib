# README Collector

Collects README file information including existence, line count, and section headings.

## Overview

This collector scans the repository root for a README.md file and extracts metadata about its contents. It checks if the file exists, counts the number of lines, and extracts section headings (headers starting with `#`). The collector runs on code changes and provides data for documentation-related policies.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.repo.readme.exists` | boolean | Whether README.md exists in the repository root |
| `.repo.readme.lines` | number | Number of lines in README.md (only present if file exists) |
| `.repo.readme.sections[]` | array | List of section headings extracted from README.md (only present if file exists) |

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

When README.md doesn't exist:

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

This collector has no configurable inputs.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/readme
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
```

## Related Policies

This collector is typically used with:
- [`readme`](https://github.com/earthly/lunar-lib/tree/main/policies/readme) - README best practices policies

