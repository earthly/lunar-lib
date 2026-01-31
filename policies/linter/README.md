# Linter Guardrails

Policies for validating that linting runs and passes with acceptable warning counts.

## Overview

This policy plugin enforces code quality standards by validating that linting tools are configured and run as part of your CI pipeline. It checks that linting was executed and that the number of warnings stays within acceptable limits, helping maintain consistent code style and catch common bugs early.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `ran` | Ensures linting was executed | Linting was not run or no linter is configured |
| `max-warnings` | Ensures lint warnings are at or below threshold | Too many lint warnings in the codebase |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.{language}.lint` | object | Language-specific linter collector |
| `.lang.{language}.lint.warnings` | array | Language-specific linter collector |

**Note:** Ensure the corresponding collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/linter@v1.0.0
    on: [go]  # Or use domain: ["domain:your-domain"]
    enforcement: report-pr
    with:
      language: "go"
      max_warnings: "0"
```

### Lenient Mode (allow some warnings)

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/linter@v1.0.0
    on: [go]
    enforcement: block-pr
    with:
      language: "go"
      max_warnings: "10"  # Allow up to 10 warnings
```

## Examples

### Passing Example

```json
{
  "lang": {
    "go": {
      "lint": {
        "warnings": []
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "go": {
      "lint": {
        "warnings": [
          {"file": "main.go", "line": 10, "message": "unused variable"}
        ]
      }
    }
  }
}
```

**Failure message:** `"Found 1 lint warning(s), maximum allowed is 0"`

## Remediation

When this policy fails, you can resolve it by:

1. **Configure a linter**: Ensure a linter collector is running (e.g., the `golang` collector with `golangci-lint`)
2. **Fix lint warnings**: Review the lint output and fix the reported issues
3. **Adjust threshold**: If adopting linting incrementally, set `max_warnings` to a higher value and reduce over time
