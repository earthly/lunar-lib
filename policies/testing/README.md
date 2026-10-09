# Testing Guardrails

Validates that tests are executed, pass, and meet coverage thresholds.

## Overview

This policy enforces that tests are executed in CI, all tests pass, and code coverage meets minimum thresholds. It is language-agnostic and works with any collector that writes to the normalized `.testing` paths (e.g., the `golang` collector for Go projects, `codecov` for coverage data).

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Tests should be executed in CI | No test execution data found |
| `passing` | All tests should pass | Tests are failing or pass/fail data unavailable |
| `coverage-collected` | Coverage data should be collected | No coverage data found |
| `coverage-reported` | Coverage percentage should be reported | Coverage runs but percentage not captured |
| `min-coverage` | Coverage should meet minimum threshold | Coverage below threshold or no coverage data |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.testing` | object | Any test collector (e.g., `golang`) |
| `.testing.all_passing` | boolean | Collectors that parse test results (e.g., `java`) |
| `.testing.runs` | array | Per-build results; when present, `passing` uses these instead of `all_passing` (e.g., `java`) |
| `.testing.coverage` | object | Any coverage collector (e.g., `codecov`, `golang`) |
| `.testing.coverage.percentage` | number | Coverage collectors that report percentage |

**Note:** All checks **fail** (not skip) when expected data is missing for a valid language project. This ensures the compliance score accurately reflects missing test/coverage data. Checks only **skip** when the component is not a language project (e.g., docs-only repos).

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/testing@main
    on: ["domain:engineering"]
    enforcement: report-pr
    include:
      - executed
      - passing
      - coverage-collected
      - coverage-reported
      - min-coverage
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
| `required_languages` | `""` | Comma-separated languages to check. If empty, applies to all components with any detected language project. Components without `.lang.*` are always skipped. |
| `min_coverage` | `"80"` | Minimum coverage percentage for the `min-coverage` check |

## Examples

### Passing Example — Full Data

Tests executed, passing, and good coverage:

```json
{
  "lang": {"go": {"version": "1.22"}},
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

When a language project exists but no test data:

```json
{
  "lang": {"go": {"version": "1.22"}}
}
```

**Failure message:** `"No test execution data found. Ensure tests are configured to run in CI."`

**Note:** All testing checks **fail** together when data is missing for a valid language project.

### Failing Example — Tests Failing (`passing` policy)

```json
{
  "lang": {"go": {"version": "1.22"}},
  "testing": {
    "all_passing": false
  }
}
```

**Failure message:** `"Tests are failing. Check CI logs for test failure details."`

With `.testing.runs`, `passing` checks every build instead of the last one to finish, keeping each build's latest CI attempt, and names the builds that failed:

```json
{
  "lang": {"java": {}},
  "testing": {
    "all_passing": true,
    "runs": [
      {"pipeline": "CI", "run_id": "100", "attempt": 1, "job": "integration", "step": 3, "total": 10, "failed": 1, "all_passing": false},
      {"pipeline": "CI", "run_id": "100", "attempt": 1, "job": "unit", "step": 3, "total": 56, "failed": 0, "all_passing": true}
    ]
  }
}
```

**Failure message:** `"Tests are failing in CI / integration (1 of 10 failed). Check CI logs for test failure details."`

On GitHub Actions every leg of a matrix job reports the same job name, so re-running one failed leg on its own replaces the other legs' results. Use **Re-run failed jobs**, which re-runs every failed leg together.

### Failing Example — Low Coverage (`min-coverage` policy)

```json
{
  "lang": {"go": {"version": "1.22"}},
  "testing": {
    "coverage": {
      "percentage": 65.0
    }
  }
}
```

**Failure message:** `"Coverage 65.0% is below minimum 80%"`

### Failing Example — No Coverage Data (`min-coverage` policy)

When coverage isn't collected but component is a valid language project:

```json
{
  "lang": {"go": {"version": "1.22"}},
  "testing": {
    "source": {"framework": "go test"}
  }
}
```

The `min-coverage` check **fails** with message: `"No coverage data collected. Configure a coverage tool to run in your CI pipeline."`

### Skipped Example — Non-Language Component

When no language project is detected (e.g., docs-only repo):

```json
{
  "repo": {"readme": {"exists": true}}
}
```

All testing checks are **skipped** with message: `"No language project detected"`

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure your CI pipeline to run tests and ensure a collector is capturing test execution data
2. **`passing` failure:** Fix the failing tests in your codebase—check CI logs for specific test failure details
3. **`coverage-collected` failure:** Configure a coverage collector to run in your CI pipeline
4. **`coverage-reported` failure:** Ensure your coverage tool is configured to report metrics (percentage)
5. **`min-coverage` failure:** Add more tests to increase code coverage, or adjust the `min_coverage` input
