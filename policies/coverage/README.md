# `coverage` Policies

Validates code coverage collection and thresholds.

## Overview

This policy enforces that code coverage data is collected in CI and meets a minimum threshold. It is vendor-agnostic and works with any coverage collector that writes to the standard `.testing.coverage` paths (e.g., Codecov, Coveralls, or custom collectors).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `collected` | Coverage data should be collected in CI | No coverage data found |
| `reported` | Coverage percentage should be reported | Coverage percentage not available |
| `min-coverage` | Coverage should meet minimum threshold | Coverage is below required percentage |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.testing.coverage` | object | Any coverage collector (e.g., `codecov`) |
| `.testing.coverage.percentage` | number | Any coverage collector |

**Note:** Object presence is the signal—the `collected` policy uses `assert_exists(".testing.coverage")` and the `reported` policy uses `assert_exists(".testing.coverage.percentage")`.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `min_coverage` | No | `80` | Minimum required coverage percentage |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/coverage@main
    on: [backend]
    enforcement: block-pr
    # include: [collected]  # Only run specific checks (omit to run all)
    # with:
    #   min_coverage: "90"
```

## Examples

### Passing Example

```json
{
  "testing": {
    "coverage": {
      "source": {
        "tool": "codecov",
        "integration": "ci"
      },
      "percentage": 85.5
    }
  }
}
```

### Failing Example

```json
{
  "testing": {
    "coverage": {
      "source": {
        "tool": "codecov",
        "integration": "ci"
      },
      "percentage": 72.0
    }
  }
}
```

**Failure message:** `"Coverage 72.0% is below minimum 80%"`

## Compatible Collectors

Any collector that writes to `.testing.coverage` can be used with this policy:

- [codecov](../../collectors/codecov) - Codecov integration

## Remediation

When this policy fails, you can resolve it by:

1. **`collected` failure:** Configure a coverage collector to run in your CI pipeline
2. **`reported` failure:** Ensure your coverage tool successfully uploads/reports coverage data
3. **`min-coverage` failure:** Add more tests to increase code coverage, or adjust the `min_coverage` input if the threshold is too aggressive
