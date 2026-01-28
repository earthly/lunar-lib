# `linter` Policies

Ensures linting runs and passes with acceptable warning counts.

## Overview

This policy enforces linting standards across programming languages. It verifies that linting was executed and that lint warnings are within acceptable limits.

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

**Note:** Ensure the corresponding collector(s) are configured before enabling this policy.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `language` | **Yes** | `""` | Programming language to check (e.g., "go", "java", "python") |
| `max_warnings` | No | `0` | Maximum lint warnings allowed (0 = no warnings allowed) |

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

### Just Check Linting Ran

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/linter@v1.0.0
    on: [go]
    include: [ran]  # Only check that linting occurred
    enforcement: block-pr
    with:
      language: "go"
```

## Examples

### Passing Example (zero warnings)

```json
{
  "lang": {
    "go": {
      "lint": {
        "warnings": [],
        "linters": ["golangci-lint"]
      }
    }
  }
}
```

### Failing Example (too many warnings)

```json
{
  "lang": {
    "go": {
      "lint": {
        "warnings": [
          {"file": "main.go", "line": 10, "message": "unused variable", "linter": "unused"},
          {"file": "util.go", "line": 25, "message": "error not checked", "linter": "errcheck"}
        ]
      }
    }
  }
}
```

**Failure message:** `"Found 2 lint warning(s), maximum allowed is 0"`

### Failing Example (linting not run)

```json
{
  "lang": {
    "go": {}
  }
}
```

**Failure message:** `"No linting data found for go. Ensure a linter is configured to run (e.g., golangci-lint for Go)."`

## Related Collectors

This policy works with any collector that populates the normalized lint data structure:

- [`golang`](https://github.com/earthly/lunar-lib/tree/main/collectors/golang) - Runs golangci-lint for Go projects

## Remediation

When this policy fails, you can resolve it by:

1. **Configure a linter**: Ensure a linter collector is running (e.g., the `golang` collector with `golangci-lint`)
2. **Fix lint warnings**: Review the lint output and fix the reported issues
3. **Adjust threshold**: If adopting linting incrementally, set `max_warnings` to a higher value and reduce over time
