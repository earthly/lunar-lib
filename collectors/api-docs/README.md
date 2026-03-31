# API Docs Collector

Detect and analyze OpenAPI/Swagger specification files in repositories.

## Overview

Searches repositories for OpenAPI and Swagger specification files by common filenames and parses their contents. Extracts the spec type (OpenAPI vs Swagger), version, validity, endpoint count, and schema count. Supports both YAML and JSON formats. Skips gracefully when no API spec files are found.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.api.spec_exists` | boolean | Whether any API spec file was found |
| `.api.specs[]` | array | List of detected API specification files |
| `.api.specs[].type` | string | Spec type: `"openapi"` or `"swagger"` |
| `.api.specs[].path` | string | File path relative to repo root |
| `.api.specs[].valid` | boolean | Whether the file parses without errors |
| `.api.specs[].version` | string | Spec version (e.g. `"3.0.3"`, `"2.0"`) |
| `.api.specs[].paths_count` | number | Number of API endpoint paths defined |
| `.api.specs[].schemas_count` | number | Number of schema definitions |
| `.api.source` | object | Source metadata (`tool`, `version`, `integration`) |

## Collectors

| Collector | Description |
|-----------|-------------|
| `api-docs` | Detects OpenAPI/Swagger spec files and extracts metadata |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/api-docs@main
    on: ["domain:your-domain"]
    # with:
    #   find_command: "find . -name 'openapi.yaml' -not -path '*/node_modules/*'"
```

