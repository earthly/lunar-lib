# OpenAPI Collector

Detect and analyze OpenAPI 3.x specification files in repositories.

## Overview

Searches repositories for OpenAPI 3.x specification files by common filenames and parses their contents. Extracts the spec version, validity, endpoint count, and schema count. Supports both YAML and JSON formats. Skips gracefully when no OpenAPI spec files are found.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.api.specs[]` | array | List of detected OpenAPI specification files (empty when none found) |
| `.api.specs[].type` | string | Always `"openapi"` |
| `.api.specs[].path` | string | File path relative to repo root |
| `.api.specs[].valid` | boolean | Whether the file parses without errors |
| `.api.specs[].version` | string | Spec version (e.g. `"3.0.3"`, `"3.1.0"`) |
| `.api.specs[].paths_count` | number | Number of API endpoint paths defined |
| `.api.specs[].schemas_count` | number | Number of schema definitions |
| `.api.source` | object | Source metadata (`tool`, `version`, `integration`) |

## Collectors

| Collector | Description |
|-----------|-------------|
| `openapi` | Detects OpenAPI 3.x spec files and extracts metadata |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/openapi@main
    on: ["domain:your-domain"]
    # with:
    #   find_command: "find . -name 'openapi.yaml' -not -path '*/node_modules/*'"
```
