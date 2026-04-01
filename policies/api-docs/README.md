# API Docs Guardrails

Enforce API documentation standards for OpenAPI/Swagger specifications.

## Overview

Validates that repositories with APIs maintain proper documentation through specification files. Operates at two levels:

- **Protocol-agnostic checks** on `.api.spec_files[]` — spec existence and validity work for any API type (REST, gRPC, GraphQL).
- **REST-specific checks** on `.api.rest.*` — endpoint and schema validation for REST APIs.

All checks skip gracefully when no API spec files are detected.

## Policies

| Policy | Description |
|--------|-------------|
| `spec-exists` | At least one API spec file detected in the repository |
| `spec-valid` | All detected spec files parse without errors |
| `spec-version-3` | All specs use OpenAPI 3.x (not deprecated Swagger 2.0) |

## Required Data

This policy reads from the following Component JSON paths:

### Protocol-Agnostic (used by all checks)

| Path | Type | Provided By |
|------|------|-------------|
| `.api.spec_files[]` | array | `openapi` / `swagger` collectors |
| `.api.spec_files[].valid` | boolean | `openapi` / `swagger` collectors |
| `.api.spec_files[].format` | string | `openapi` / `swagger` collectors |

### REST-Specific (available for future endpoint/schema checks)

| Path | Type | Provided By |
|------|------|-------------|
| `.api.rest.endpoints[]` | array | `openapi` / `swagger` collectors |
| `.api.rest.schemas[]` | array | `openapi` / `swagger` collectors |
| `.api.rest.native.openapi` | object | `openapi` collector |
| `.api.rest.native.swagger` | object | `swagger` collector |

**Note:** Enable at least one of the `openapi` or `swagger` collectors before using this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/api-docs@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [spec-exists]  # Only run specific checks (omit to run all)
```

## Examples

### Passing Example

Repository with a valid OpenAPI 3.x spec:

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
        "schema_count": 5
      }
    ],
    "rest": {
      "endpoints": [
        {
          "path": "/users",
          "method": "GET",
          "operation_id": "listUsers",
          "summary": "List all users",
          "tags": ["users"]
        }
      ],
      "schemas": [
        {
          "name": "User",
          "type": "object",
          "property_count": 4,
          "required_count": 2,
          "properties": ["id", "email", "name", "created_at"]
        }
      ]
    }
  }
}
```

### Failing Example — No Spec

Repository with no API spec files:

```json
{}
```

**Failure message:** `"No API specification file found"`

### Failing Example — Invalid Spec

```json
{
  "api": {
    "spec_files": [
      {
        "path": "api/openapi.yaml",
        "format": "openapi",
        "protocol": "rest",
        "valid": false,
        "version": null,
        "operation_count": 0,
        "schema_count": 0
      }
    ]
  }
}
```

**Failure message:** `"API spec file api/openapi.yaml failed to parse"`

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
        "schema_count": 3
      }
    ]
  }
}
```

**Failure message:** `"API spec swagger.json uses Swagger 2.0 — migrate to OpenAPI 3.x"`

## Remediation

When these policies fail, you can resolve them by:

1. **spec-exists:** Add an OpenAPI or Swagger specification file to your repository (e.g. `openapi.yaml`).
2. **spec-valid:** Fix syntax errors in your spec file. Use a linter like [Spectral](https://github.com/stoplightio/spectral) to validate.
3. **spec-version-3:** Migrate from Swagger 2.0 to OpenAPI 3.x using a tool like [swagger2openapi](https://github.com/Mermade/oas-kit/tree/main/packages/swagger2openapi).
