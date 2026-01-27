# `codecov` Policies

Validates Codecov usage and coverage thresholds.

## Overview

This policy enforces that Codecov runs in CI and that code coverage meets a minimum threshold. Use it to ensure coverage data is being collected and that your codebase maintains adequate test coverage.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `ran` | Codecov should run in CI | Codecov was not detected in CI |
| `uploaded` | Codecov upload should run in CI | Codecov upload was not detected in CI |
| `min-coverage` | Coverage should meet minimum threshold | Coverage is below required percentage |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.testing.codecov.detected` | boolean | `codecov` collector (`ran` sub-collector) |
| `.testing.codecov.uploaded` | boolean | `codecov` collector (`results` sub-collector) |
| `.testing.codecov.results.coverage` | number | `codecov` collector (`results` sub-collector) |

**Note:** Ensure the `codecov` collector is configured before enabling this policy.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `min_coverage` | No | `80` | Minimum required coverage percentage |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/codecov@main
    on: [backend]
    enforcement: block-pr
    # include: [ran]  # Only run specific checks (omit to run all)
    # with:
    #   min_coverage: "90"
```

## Examples

### Passing Example

```json
{
  "testing": {
    "codecov": {
      "detected": true,
      "uploaded": true,
      "results": {
        "coverage": 85.5
      }
    }
  }
}
```

### Failing Example

```json
{
  "testing": {
    "codecov": {
      "detected": true,
      "uploaded": true,
      "results": {
        "coverage": 72.0
      }
    }
  }
}
```

**Failure message:** `"Coverage 72.0% is below minimum 80%"`

## Related Collectors

- [codecov](../../collectors/codecov) - Detects Codecov usage and fetches coverage results from the API

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codecov@main
    on: [backend]
```

## Remediation

When this policy fails, you can resolve it by:

1. **`ran` failure:** Ensure Codecov CLI is installed and runs in your CI pipeline after tests complete
2. **`uploaded` failure:** Ensure your CI pipeline runs a codecov upload command (`upload`, `do-upload`, or `upload-process`)
3. **`min-coverage` failure:** Add more tests to increase code coverage to meet the threshold, or adjust the `min_coverage` input if the threshold is too aggressive
