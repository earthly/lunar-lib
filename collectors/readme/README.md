# README Collector

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

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/readme@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:
    #   path: "README.md,docs/README.md"  # Customize which files to check
```

