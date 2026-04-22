# SonarQube Guardrails

SonarQube/SonarCloud-specific code-quality checks — quality gate and letter-rating thresholds.

## Overview

Enforces SonarQube's native affordances — quality-gate `OK` status with zero failed conditions, and letter-rating minimums (A–E, A best) for reliability, security, and maintainability. Skips cleanly when SonarQube data is absent for a component, so it's safe to apply broadly. For tool-agnostic checks that apply across any code-quality scanner (SonarQube, CodeClimate, Codacy), use the `code-quality` policy instead.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `quality-gate-passing` | Quality gate is `OK` with zero failed conditions | Gate `status` is `WARN`/`ERROR` or conditions failed |
| `min-reliability-rating` | Reliability rating meets minimum | Rating worse than configured letter |
| `min-security-rating` | Security rating meets minimum | Rating worse than configured letter |
| `min-maintainability-rating` | Maintainability rating meets minimum | Rating worse than configured letter |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.code_quality.native.sonarqube.quality_gate.status` | string | `sonarqube` collector (`api-default`, `api-pr`, `auto-default`, or `auto-pr` sub-collector) |
| `.code_quality.native.sonarqube.quality_gate.conditions_failed` | number | `sonarqube` collector (`api-default`, `api-pr`, `auto-default`, or `auto-pr` sub-collector) |
| `.code_quality.native.sonarqube.ratings.reliability` | string | `sonarqube` collector (`api-default`, `api-pr`, `auto-default`, or `auto-pr` sub-collector) |
| `.code_quality.native.sonarqube.ratings.security` | string | `sonarqube` collector (`api-default`, `api-pr`, `auto-default`, or `auto-pr` sub-collector) |
| `.code_quality.native.sonarqube.ratings.maintainability` | string | `sonarqube` collector (`api-default`, `api-pr`, `auto-default`, or `auto-pr` sub-collector) |

**Note:** All checks skip if `.code_quality.native.sonarqube` is absent — components without SonarQube configured will not fail. Apply the `code-quality` policy alongside this one to enforce "a scanner ran" regardless of which tool.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/sonarqube@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [quality-gate-passing]  # Only run specific checks
    with:
      min_reliability_rating: "A"       # Fail if reliability is B or worse
      min_security_rating: "A"          # Fail if security is B or worse
      min_maintainability_rating: "B"   # Fail if maintainability is C or worse
```

## Examples

### Passing Example

```json
{
  "code_quality": {
    "native": {
      "sonarqube": {
        "quality_gate": { "status": "OK", "conditions_failed": 0 },
        "ratings": {
          "reliability": "A",
          "security": "A",
          "maintainability": "B"
        }
      }
    }
  }
}
```

### Failing Example

```json
{
  "code_quality": {
    "native": {
      "sonarqube": {
        "quality_gate": { "status": "ERROR", "conditions_failed": 3 },
        "ratings": {
          "reliability": "C",
          "security": "B",
          "maintainability": "D"
        }
      }
    }
  }
}
```

**Failure messages:**
- `quality-gate-passing`: "SonarQube quality gate failed (status=ERROR, 3 conditions failed)"
- `min-reliability-rating`: "Reliability rating C is below minimum A"
- `min-security-rating`: "Security rating B is below minimum A"
- `min-maintainability-rating`: "Maintainability rating D is below minimum B"

## Remediation

When this policy fails, you can resolve it by:

1. **`quality-gate-passing` failure:** Review the failed conditions in the SonarQube UI and fix the flagged issues (new bugs, new vulnerabilities, coverage on new code, etc.).
2. **`min-reliability-rating` failure:** Address the bugs SonarQube reports in the **Reliability** dimension.
3. **`min-security-rating` failure:** Address the vulnerabilities in the **Security** dimension.
4. **`min-maintainability-rating` failure:** Reduce technical debt by resolving code smells (the SQALE rating).
