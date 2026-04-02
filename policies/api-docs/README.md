# API Docs Guardrails

Enforce API documentation standards for OpenAPI/Swagger specifications.

## Overview

Validates that repositories with APIs maintain proper documentation through specification files. Operates on protocol-agnostic `.api.spec_files[]` — all checks work for any API type (REST, gRPC, GraphQL). Deep inspection uses raw native specs under `.api.native.*`.

All checks skip gracefully when no API spec files are detected.

## Policies

| Policy | Description |
|--------|-------------|
| `spec-exists` | At least one API spec file detected in the repository |
| `spec-valid` | All detected spec files parse without errors |
| `has-docs` | All spec files include human-readable documentation (descriptions, examples) |
| `spec-version-3` | All specs use OpenAPI 3.x (not deprecated Swagger 2.0) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.api.spec_files[]` | array | `openapi` collector |
| `.api.spec_files[].valid` | boolean | `openapi` collector |
| `.api.spec_files[].format` | string | `openapi` collector |
| `.api.spec_files[].has_docs` | boolean | `openapi` collector |

**Note:** Enable the `openapi` collector before using this policy. It handles both OpenAPI 3.x and Swagger 2.0.

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

Repository with a valid, documented OpenAPI 3.x spec:

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
    ],
    "native": {
      "openapi": {
        "api/openapi.yaml": { "...": "full raw spec" }
      }
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
        "schema_count": 0,
        "has_docs": false
      }
    ]
  }
}
```

**Failure message:** `"API spec file api/openapi.yaml failed to parse"`

### Failing Example — No Documentation

A bare spec with no descriptions or examples:

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
        "operation_count": 8,
        "schema_count": 3,
        "has_docs": false
      }
    ]
  }
}
```

**Failure message:** `"API spec api/openapi.yaml has no documentation (descriptions, examples)"`

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

**Failure message:** `"API spec swagger.json uses Swagger 2.0 — migrate to OpenAPI 3.x"`

## Remediation

When these policies fail, you can resolve them by:

1. **spec-exists:** Add an OpenAPI or Swagger specification file to your repository (e.g. `openapi.yaml`).
2. **spec-valid:** Fix syntax errors in your spec file. Use a linter like [Spectral](https://github.com/stoplightio/spectral) to validate.
3. **has-docs:** Add `description` fields to your operations, schemas, and parameters. Use `example` or `examples` to document expected values.
4. **spec-version-3:** Migrate from Swagger 2.0 to OpenAPI 3.x using a tool like [swagger2openapi](https://github.com/Mermade/oas-kit/tree/main/packages/swagger2openapi).
