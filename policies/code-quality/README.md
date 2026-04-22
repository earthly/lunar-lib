# Code Quality Guardrails

Enforce code-quality standards across any scanner that writes to `.code_quality`.

## Overview

Validates that a code-quality scanner ran, the tool's overall pass/fail signal is green, and that coverage, duplication, and severity-bucketed issue counts meet configurable thresholds. Works with any scanner that writes to the tool-agnostic `.code_quality` path — SonarQube today, CodeClimate / Codacy / DeepSource in principle. Apply broadly as a "code quality happens" guardrail, or bring-your-own thresholds per domain.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `executed` | Verifies a code-quality scanner ran | No scanner has written to `.code_quality` |
| `passing` | Tool's pass/fail signal is green | `.code_quality.passing` is `false` (quality gate failed) |
| `min-coverage` | Line-coverage meets minimum | Coverage below configured threshold or missing |
| `max-duplication` | Duplicated-lines under threshold | Duplication above configured threshold |
| `max-severity` | No issues at or above severity threshold | Issues found at configured severity or higher |
| `max-total` | Total issues under threshold | Total issue count exceeds configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.code_quality` | object | Any code-quality collector (SonarQube, etc.) |
| `.code_quality.passing` | bool | Code-quality collector (derived from the tool's quality gate) |
| `.code_quality.coverage_percentage` | number | Code-quality collector |
| `.code_quality.duplication_percentage` | number | Code-quality collector |
| `.code_quality.issue_counts.total` | number | Code-quality collector |
| `.code_quality.issue_counts.critical` | number | Code-quality collector |
| `.code_quality.issue_counts.high` | number | Code-quality collector |
| `.code_quality.issue_counts.medium` | number | Code-quality collector |
| `.code_quality.issue_counts.low` | number | Code-quality collector |

**Note:** If collectors don't yet write issue counts or coverage, the corresponding checks will fail. Use `include: [executed, passing]` to only verify the scanner ran and is green until more fields land.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/code-quality@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [executed, passing]  # Only run specific checks
    with:
      min_severity: "high"                  # Fail on critical and high issues
      max_total_threshold: "50"             # Fail if more than 50 total issues
      min_coverage_percentage: "80"         # Fail under 80% line coverage
      max_duplication_percentage: "5"       # Fail above 5% duplicated lines
```

## Examples

### Passing Example

```json
{
  "code_quality": {
    "source": { "tool": "sonarqube", "integration": "branch" },
    "passing": true,
    "coverage_percentage": 82.5,
    "duplication_percentage": 3.1,
    "issue_counts": { "total": 12, "critical": 0, "high": 0, "medium": 2, "low": 10 }
  }
}
```

### Failing Example

```json
{
  "code_quality": {
    "source": { "tool": "sonarqube", "integration": "branch" },
    "passing": false,
    "coverage_percentage": 61.4,
    "duplication_percentage": 8.2,
    "issue_counts": { "total": 120, "critical": 2, "high": 5, "medium": 30, "low": 83 }
  }
}
```

**Failure messages:**
- `executed`: "No code-quality scanning data found. Ensure a scanner (SonarQube, etc.) is configured."
- `passing`: "Code-quality gate failed (.code_quality.passing is false)"
- `min-coverage`: "Line coverage 61.4% is below minimum 80%"
- `max-duplication`: "Duplication 8.2% exceeds maximum 5%"
- `max-severity`: "Critical code-quality issues detected (2 found)"
- `max-total`: "Total code-quality issues (120) exceeds threshold (50)"

## Remediation

When this policy fails, you can resolve it by:

1. **`executed` failure:** Configure a code-quality scanner (SonarQube, CodeClimate, etc.) in CI or as a scheduled API collector.
2. **`passing` failure:** Fix the specific quality-gate conditions flagged by the scanner.
3. **`min-coverage` failure:** Add tests or configure coverage reporting for uncovered code paths.
4. **`max-duplication` failure:** Refactor duplicated blocks into shared helpers.
5. **`max-severity` failure:** Address issues at or above the configured severity in the scanner UI.
6. **`max-total` failure:** Reduce overall issue count by fixing or acknowledging flagged items.
