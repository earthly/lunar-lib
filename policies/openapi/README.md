# OpenAPI Guardrails

Enforce OpenAPI and Swagger specification standards for REST APIs.

## Overview

OpenAPI-specific policy checks that operate on `.api.spec_files[]` entries with `protocol: "rest"`. For protocol-agnostic checks (spec exists, spec valid, has docs), see the `api-docs` policy.

## Policies

| Policy | Description |
|--------|-------------|
| `spec-version` | Ensures all REST specs meet a minimum OpenAPI version (default: 3), flags older specs |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.api.spec_files[]` | array | `openapi` collector |
| `.api.spec_files[].version` | string | `openapi` collector |
| `.api.spec_files[].protocol` | string | `openapi` collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/openapi@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # with:
    #   min_version: "3"  # default — require OpenAPI 3.x+
```

Requires the `openapi` collector to be enabled.

## Examples

### Passing Example

Repository with OpenAPI 3.x spec:

```json
{
  "api": {
    "spec_files": [
      {
        "path": "api/openapi.yaml",
        "format": "openapi",
        "protocol": "rest",
        "valid": true,
        "version": "3.0.3",
        "operation_count": 12,
        "schema_count": 5,
        "has_docs": true
      }
    ]
  }
}
```

### Failing Example — Swagger 2.0

```json
{
  "api": {
    "spec_files": [
      {
        "path": "swagger.json",
        "format": "swagger",
        "protocol": "rest",
        "valid": true,
        "version": "2.0",
        "operation_count": 8,
        "schema_count": 3,
        "has_docs": true
      }
    ]
  }
}
```

**Failure message:** `"swagger.json uses version 2.0 — minimum required is 3"`

## Remediation

### spec-version
1. Migrate from Swagger 2.0 to OpenAPI 3.x using a tool like [swagger2openapi](https://github.com/Mermade/oas-kit/tree/main/packages/swagger2openapi)
2. Key changes: `host`/`basePath` → `servers[]`, `definitions` → `components/schemas`, `produces`/`consumes` → per-operation `content` types
3. Validate the migrated spec with [Spectral](https://github.com/stoplightio/spectral)
