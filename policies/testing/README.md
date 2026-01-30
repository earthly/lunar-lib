# Testing Policies

Validates that tests are executed and pass.

## Overview

This policy enforces that tests are executed in CI and all tests pass. It is language-agnostic and works with any collector that writes to the normalized `.testing` paths (e.g., the `golang` collector for Go projects).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Tests should be executed in CI | No test execution data found |
| `passing` | All tests should pass | Tests are failing (or skipped if pass/fail data unavailable) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.testing` | object | Any test collector (e.g., `golang`) |
| `.testing.all_passing` | boolean | Collectors that parse test results |

**Note:** The `passing` check will **skip** (not fail) if `.testing.all_passing` is not available. This is intentional—some collectors only report that tests were executed, not detailed results. Use the `executed` check alone if your collector doesn't provide pass/fail data.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/testing@main
    on: ["domain:engineering"]
    enforcement: report-pr
    # include: [executed]  # Only run specific checks (omit to run all)
    with:
      # required_languages: Only enforce for components with detected language projects
      # Checks for .lang.<language> existence (set by language collectors)
      # Skips docs-only repos, infrastructure components, repos that just run scripts
      required_languages: "go,python,nodejs,java"
```

**Input: `required_languages`** (default: empty = applies to all)

Comma-separated list of languages. Components without a detected project for any of these languages will be skipped. This prevents false failures on repos that don't have a supported test collector.

## Examples

### Passing Example

Tests executed and all passing:

```json
{
  "testing": {
    "source": {
      "framework": "go test",
      "integration": "ci"
    },
    "results": {
      "total": 156,
      "passed": 156,
      "failed": 0,
      "skipped": 0
    },
    "all_passing": true
  }
}
```

### Failing Example — No Tests Executed

```json
{}
```

**Failure message:** `"No test execution data found. Ensure tests are configured to run in CI."`

### Failing Example — Tests Failing

```json
{
  "testing": {
    "source": {
      "framework": "go test",
      "integration": "ci"
    },
    "results": {
      "total": 156,
      "passed": 154,
      "failed": 2,
      "skipped": 0
    },
    "all_passing": false
  }
}
```

**Failure message:** `"Tests are failing. Check CI logs for test failure details."`

### Skipped Example — No Pass/Fail Data

When the collector only reports test execution (not results):

```json
{
  "testing": {
    "source": {
      "framework": "go test",
      "integration": "ci"
    }
  }
}
```

The `executed` check passes, but `passing` is **skipped** with message: `"Test pass/fail data not available. This requires a collector that reports detailed test results."`

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure your CI pipeline to run tests and ensure a collector is capturing test execution data
2. **`passing` failure:** Fix the failing tests in your codebase—check CI logs for specific test failure details
