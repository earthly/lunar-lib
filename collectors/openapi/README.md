# OpenAPI Collector

Detect and analyze OpenAPI 3.x and Swagger 2.0 specification files in repositories.

## Overview

Searches repositories for OpenAPI and Swagger specification files by common filenames and parses their contents. Extracts normalized endpoint and schema data for REST API analysis, and stores the full raw spec for deep inspection. Supports both YAML and JSON formats. Skips gracefully when no spec files are found.

OpenAPI is the evolution of the Swagger specification — Swagger 2.0 was renamed to OpenAPI 3.0 when the spec was donated to the OpenAPI Initiative. This collector handles both naming conventions (`openapi.yaml`/`openapi.json` and `swagger.yaml`/`swagger.json`) in a single pass, normalizing both formats into the same `.api.rest` structure.

## Collected Data

This collector writes to the following Component JSON paths:

### Protocol-Agnostic (`.api.spec_files[]`)

| Path | Type | Description |
|------|------|-------------|
| `.api.spec_files[]` | array | Spec file metadata (one entry per spec file found) |
| `.api.spec_files[].path` | string | File path relative to repo root |
| `.api.spec_files[].format` | string | `"openapi"` for OpenAPI 3.x, `"swagger"` for Swagger 2.0 |
| `.api.spec_files[].protocol` | string | Always `"rest"` |
| `.api.spec_files[].valid` | boolean | Whether the file parses without errors |
| `.api.spec_files[].version` | string | Spec version (e.g. `"3.0.3"`, `"3.1.0"`, `"2.0"`) |
| `.api.spec_files[].operation_count` | number | Number of operations (path + method combinations) |
| `.api.spec_files[].schema_count` | number | Number of schema/definition entries |

### REST-Specific Normalized (`.api.rest.*`)

| Path | Type | Description |
|------|------|-------------|
| `.api.rest.endpoints[]` | array | Normalized REST endpoints extracted from the spec |
| `.api.rest.endpoints[].path` | string | URL path (e.g. `"/users/{id}"`) |
| `.api.rest.endpoints[].method` | string | HTTP method (`"GET"`, `"POST"`, etc.) |
| `.api.rest.endpoints[].operation_id` | string | Operation identifier |
| `.api.rest.endpoints[].summary` | string | Short description |
| `.api.rest.endpoints[].tags` | array | Grouping tags |
| `.api.rest.endpoints[].parameters[]` | array | Path/query/header parameters |
| `.api.rest.endpoints[].request_body` | string | Request body schema name |
| `.api.rest.schemas[]` | array | Normalized schema definitions |
| `.api.rest.schemas[].name` | string | Schema name |
| `.api.rest.schemas[].type` | string | Schema type (`"object"`, `"array"`, etc.) |
| `.api.rest.schemas[].property_count` | number | Number of properties |
| `.api.rest.schemas[].required_count` | number | Number of required properties |
| `.api.rest.schemas[].properties` | array | List of property names |

### Native/Raw (`.api.rest.native.*`)

| Path | Type | Description |
|------|------|-------------|
| `.api.rest.native.openapi` | object | The entire raw OpenAPI 3.x spec converted to JSON |
| `.api.rest.native.swagger` | object | The entire raw Swagger 2.0 spec converted to JSON |

## Supported Formats

| Format | File Patterns | Spec Version | Native Path |
|--------|--------------|--------------|-------------|
| OpenAPI 3.x | `openapi.yaml`, `openapi.yml`, `openapi.json` | 3.0.x, 3.1.x | `.api.rest.native.openapi` |
| Swagger 2.0 | `swagger.yaml`, `swagger.yml`, `swagger.json` | 2.0 | `.api.rest.native.swagger` |

Both formats produce the same normalized output under `.api.rest.endpoints[]` and `.api.rest.schemas[]`. The `format` field in `.api.spec_files[]` distinguishes the source.

## Collectors

| Collector | Description |
|-----------|-------------|
| `openapi` | Detects OpenAPI 3.x and Swagger 2.0 spec files, extracts metadata, endpoints, schemas, and raw specs |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/openapi@main
    on: ["domain:your-domain"]
    # with:
    #   find_command: "find . -name 'openapi.yaml' -not -path '*/node_modules/*'"
```
