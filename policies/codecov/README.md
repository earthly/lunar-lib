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
| `.testing.coverage` | object | `codecov` collector (`ran` sub-collector) |
| `.testing.coverage.percentage` | number | `codecov` collector (`results` sub-collector) |
| `.testing.coverage.native.codecov` | object | Full API response (for custom policies) |

**Note:** Object presence is the signal—the `ran` policy uses `assert_exists(".testing.coverage")` and the `uploaded` policy uses `assert_exists(".testing.coverage.percentage")`.

**Note:** The `.native.codecov` field contains the full Codecov API response for custom policies that need additional fields (e.g., `files`, `lines`, `hits`, `misses`).

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

## Related Collectors

- [codecov](../../collectors/codecov) - Detects Codecov usage and fetches coverage results from the API

## Remediation

When this policy fails, you can resolve it by:

1. **`ran` failure:** Ensure Codecov CLI is installed and runs in your CI pipeline after tests complete
2. **`uploaded` failure:** Ensure your CI pipeline runs a codecov upload command (`upload`, `do-upload`, or `upload-process`)
3. **`min-coverage` failure:** Add more tests to increase code coverage to meet the threshold, or adjust the `min_coverage` input if the threshold is too aggressive
