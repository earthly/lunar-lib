# Testing Guardrails

Validates that tests are executed, pass, and meet coverage thresholds.

## Overview

This policy enforces that tests are executed in CI, all tests pass, and code coverage meets minimum thresholds. It is language-agnostic and works with any collector that writes to the normalized `.testing` paths (e.g., the `golang` collector for Go projects, `codecov` for coverage data).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Tests should be executed in CI | No test execution data found |
| `passing` | All tests should pass | Tests are failing (or skipped if pass/fail data unavailable) |
| `coverage-collected` | Coverage data should be collected | No coverage data found |
| `coverage-reported` | Coverage percentage should be reported | Coverage runs but percentage not captured |
| `min-coverage` | Coverage should meet minimum threshold | Coverage below required percentage (or skipped if no data) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.testing` | object | Any test collector (e.g., `golang`) |
| `.testing.all_passing` | boolean | Collectors that parse test results |
| `.testing.coverage` | object | Any coverage collector (e.g., `codecov`, `golang`) |
| `.testing.coverage.percentage` | number | Coverage collectors that report percentage |

**Note:** The `passing` and `min-coverage` checks will **skip** (not fail) if their required data is not available. This is intentional—some collectors only report partial data. Use `coverage-reported` if you want to **enforce** that percentage is reported.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/testing@main
    on: ["domain:engineering"]
    enforcement: report-pr
    # include: [executed, passing]  # Only run specific checks (omit to run all)
    with:
      # required_languages: Only enforce for components with detected language projects
      # Checks for .lang.<language> existence (set by language collectors)
      # Skips docs-only repos, infrastructure components, repos that just run scripts
      required_languages: "go,python,nodejs,java"
      # min_coverage: Minimum coverage percentage for min-coverage check
      min_coverage: "80"
```

**Inputs:**

| Input | Default | Description |
|-------|---------|-------------|
| `required_languages` | `""` | Comma-separated languages. Components without a matching `.lang.<lang>` project are skipped. |
| `min_coverage` | `"80"` | Minimum coverage percentage for the `min-coverage` check |

## Examples

### Passing Example — Full Data

Tests executed, passing, and good coverage:

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
    "all_passing": true,
    "coverage": {
      "percentage": 85.5
    }
  }
}
```

### Failing Example — No Tests Executed (`executed` policy)

```json
{}
```

**Failure message:** `"No test execution data found. Ensure tests are configured to run in CI."`

**Note:** The `passing` policy **skips** in this case with: `"No test execution data found"`

### Failing Example — Tests Failing (`passing` policy)

```json
{
  "testing": {
    "all_passing": false
  }
}
```

**Failure message:** `"Tests are failing. Check CI logs for test failure details."`

### Failing Example — Low Coverage (`min-coverage` policy)

```json
{
  "testing": {
    "coverage": {
      "percentage": 65.0
    }
  }
}
```

**Failure message:** `"Coverage 65.0% is below minimum 80%"`

### Skipped Example — No Coverage Data (`min-coverage` policy)

When coverage isn't collected:

```json
{
  "testing": {
    "source": {"framework": "go test"}
  }
}
```

The `min-coverage` check is **skipped** with message: `"No coverage data available"`

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure your CI pipeline to run tests and ensure a collector is capturing test execution data
2. **`passing` failure:** Fix the failing tests in your codebase—check CI logs for specific test failure details
3. **`coverage-collected` failure:** Configure a coverage collector to run in your CI pipeline
4. **`coverage-reported` failure:** Ensure your coverage tool is configured to report metrics (percentage)
5. **`min-coverage` failure:** Add more tests to increase code coverage, or adjust the `min_coverage` input
