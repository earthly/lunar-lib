# API Docs Guardrails

Enforce API documentation standards for OpenAPI/Swagger specifications.

## Overview

Validates that repositories with APIs maintain proper documentation through OpenAPI or Swagger specification files. Checks for spec file existence, syntax validity, and encourages migration from deprecated Swagger 2.0 to OpenAPI 3.x. All checks skip gracefully when no API spec files are detected.

## Policies

| Policy | Description |
|--------|-------------|
| `spec-exists` | OpenAPI/Swagger spec file detected in the repository |
| `spec-valid` | All detected spec files parse without errors |
| `spec-version-3` | All specs use OpenAPI 3.x (not deprecated Swagger 2.0) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.api.spec_exists` | boolean | `api-docs` collector |
| `.api.specs[]` | array | `api-docs` collector |
| `.api.specs[].valid` | boolean | `api-docs` collector |
| `.api.specs[].version` | string | `api-docs` collector |

**Note:** Ensure the `api-docs` collector is configured before enabling this policy.

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
    "spec_exists": true,
    "specs": [
      {
        "type": "openapi",
        "path": "api/openapi.yaml",
        "valid": true,
        "version": "3.0.3"
      }
    ]
  }
}
```

### Failing Example — No Spec

Repository with no API spec files:

```json
{
  "api": {
    "spec_exists": false
  }
}
```

**Failure message:** `"No OpenAPI or Swagger specification file found"`

### Failing Example — Invalid Spec

```json
{
  "api": {
    "spec_exists": true,
    "specs": [
      {
        "type": "openapi",
        "path": "api/openapi.yaml",
        "valid": false,
        "version": null
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
    "spec_exists": true,
    "specs": [
      {
        "type": "swagger",
        "path": "swagger.json",
        "valid": true,
        "version": "2.0"
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
