# OpenAPI Collector

Detect and analyze OpenAPI and Swagger specification files in repositories (any version).

## Overview

Searches repositories for OpenAPI and Swagger specification files by common filenames and parses their contents. Stores the full raw spec under `.api.native.openapi` for deep inspection, and writes protocol-agnostic metadata to `.api.spec_files[]`. Supports both YAML and JSON formats. OpenAPI is the evolution of the Swagger specification — Swagger 2.0 was renamed to OpenAPI 3.0 when donated to the OpenAPI Initiative. This collector handles both naming conventions (`openapi.yaml`/`openapi.json` and `swagger.yaml`/`swagger.json`) in a single pass.

## Collected Data

This collector writes to the following Component JSON paths:

### Protocol-Agnostic (`.api.spec_files[]`)

| Path | Type | Description |
|------|------|-------------|
| `.api.spec_files[]` | array | Spec file metadata (one entry per spec file found) |
| `.api.spec_files[].path` | string | File path relative to repo root |
| `.api.spec_files[].format` | string | `"openapi"` for OpenAPI 3.x+, `"swagger"` for Swagger 1.x/2.0 |
| `.api.spec_files[].protocol` | string | Always `"rest"` |
| `.api.spec_files[].valid` | boolean | Whether the file parses without errors |
| `.api.spec_files[].version` | string | Spec version (e.g. `"3.0.3"`, `"3.1.0"`, `"2.0"`) |
| `.api.spec_files[].operation_count` | number | Number of operations (path + method combinations) |
| `.api.spec_files[].schema_count` | number | Number of schema/definition entries |
| `.api.spec_files[].has_docs` | boolean | Always `true` for OpenAPI/Swagger — these specs inherently contain human-readable documentation |

### Native/Raw (`.api.native.openapi`)

| Path | Type | Description |
|------|------|-------------|
| `.api.native.openapi` | object | Map of file path → raw spec as JSON. All versions live here (same spec lineage) |

**File patterns:** OpenAPI 3.x (`openapi.yaml`, `openapi.yml`, `openapi.json`) and Swagger 2.0 (`swagger.yaml`, `swagger.yml`, `swagger.json`).

## Collectors

| Collector | Description |
|-----------|-------------|
| `openapi` | Detects OpenAPI and Swagger spec files (any version), extracts metadata and raw specs |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/openapi@main
    on: ["domain:your-domain"]
    # with:
    #   find_command: "find . -name 'openapi.yaml' -not -path '*/node_modules/*'"
```
