# Compliance Documentation Guardrails

Enforces that required compliance documentation exists, is kept current, and contains required sections.

## Overview

This policy plugin verifies that services maintain required compliance documentation. It covers disaster recovery plans (recovery procedures, RTO/RPO) and a history of DR exercise records (tabletop exercises, failover tests). These policies support compliance frameworks (SOC 2, ISO 27001, NIST) that mandate documented and tested DR procedures.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `dr-plan-exists` | Ensures DR plan document exists in the repository | No DR plan found at expected path |
| `dr-plan-rto-rpo-defined` | Ensures RTO and RPO values are documented in the plan | Recovery objectives missing from plan frontmatter |
| `dr-plan-required-sections` | Ensures DR plan contains required sections | Plan is missing one or more required sections |
| `dr-exercise-recent` | Ensures a DR exercise was conducted within threshold | No exercises found or last exercise is too old |
| `dr-exercise-required-sections` | Ensures DR exercise records contain required sections (latest or all, via `exercises_check_all`) | Exercise is missing one or more required sections |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.oncall.disaster_recovery.plan.exists` | boolean | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.plan.rto_defined` | boolean | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.plan.rpo_defined` | boolean | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.plan.sections` | array | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.exercises[]` | array | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.latest_exercise_date` | string | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.exercise_count` | number | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |

**Note:** Ensure the corresponding collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/compliance-docs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [production, tier1]
    enforcement: report-pr      # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include: [dr-plan-exists, dr-exercise-recent]  # Only run specific checks
    # with:
    #   max_days_since_exercise: "365"
    #   plan_required_sections: "Overview,Recovery Steps,Contact List"
    #   exercise_required_sections: "Scenario,Recovery Steps Tested,Participants"
    #   exercises_check_all: "false"  # Check sections on all exercises (true) or latest only (false)
```

## Examples

### Passing Example

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan": {
        "exists": true,
        "path": "docs/dr-plan.md",
        "rto_defined": true,
        "rto_minutes": 60,
        "rpo_defined": true,
        "rpo_minutes": 15,
        "sections": ["Overview", "Recovery Steps", "Contact List", "Dependencies"]
      },
      "exercises": [
        {
          "date": "2025-11-15",
          "path": "docs/dr-exercises/2025-11-15.md",
          "exercise_type": "tabletop",
          "sections": ["Scenario", "Recovery Steps Tested", "Participants", "Action Items"]
        }
      ],
      "latest_exercise_date": "2025-11-15",
      "exercise_count": 1
    }
  }
}
```

This example passes all five policies with default configuration.

### Failing Examples

#### DR plan missing (fails `dr-plan-exists`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan": { "exists": false }
    }
  }
}
```

**Failure message:** `"DR plan not found (expected docs/dr-plan.md)"`

#### Recovery objectives missing (fails `dr-plan-rto-rpo-defined`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan": {
        "exists": true,
        "path": "docs/dr-plan.md",
        "rto_defined": false,
        "rpo_defined": false,
        "sections": ["Overview", "Recovery Steps", "Contact List"]
      }
    }
  }
}
```

**Failure message:** `"Recovery objectives not defined — add rto_minutes and rpo_minutes to DR plan frontmatter"`

#### No exercises found (fails `dr-exercise-recent`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "exercises": [],
      "exercise_count": 0
    }
  }
}
```

**Failure message:** `"No DR exercise records found — create docs/dr-exercises/YYYY-MM-DD.md"`

#### Exercise overdue (fails `dr-exercise-recent`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "exercises": [
        {
          "date": "2024-06-01",
          "path": "docs/dr-exercises/2024-06-01.md",
          "sections": ["Scenario", "Recovery Steps Tested", "Participants"]
        }
      ],
      "latest_exercise_date": "2024-06-01",
      "exercise_count": 1
    }
  }
}
```

**Failure message:** `"Last DR exercise was 622 days ago (maximum allowed: 365)"`

#### Latest exercise missing sections (fails `dr-exercise-required-sections`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "exercises": [
        {
          "date": "2025-11-15",
          "path": "docs/dr-exercises/2025-11-15.md",
          "sections": ["Scenario"]
        }
      ],
      "latest_exercise_date": "2025-11-15",
      "exercise_count": 1
    }
  }
}
```

**Failure message:** `"Latest DR exercise (2025-11-15) is missing required sections: Recovery Steps Tested, Participants"`

## Remediation

### dr-plan-exists

Create a disaster recovery plan at `docs/dr-plan.md` (or your configured path):

```markdown
---
rto_minutes: 60
rpo_minutes: 15
last_reviewed: 2025-12-01
approver: jane.doe@company.com
---

# Disaster Recovery Plan

## Overview
This document describes the DR procedures for this service...

## Recovery Steps
1. Verify the incident scope...
2. Initiate failover to secondary region...

## Contact List
- Primary on-call: ...
- Engineering manager: ...

## Dependencies
- PostgreSQL (RDS Multi-AZ)
- Redis (ElastiCache)
```

### dr-plan-rto-rpo-defined

Add `rto_minutes` and `rpo_minutes` to the DR plan's YAML frontmatter:
- **RTO (Recovery Time Objective)**: Maximum acceptable time from disaster to service restoration. Example: `rto_minutes: 60` means restore within 1 hour.
- **RPO (Recovery Point Objective)**: Maximum acceptable data loss measured in time. Example: `rpo_minutes: 15` means no more than 15 minutes of data loss.

### dr-plan-required-sections

Add the missing section headings to the DR plan. Default required sections are Overview, Recovery Steps, and Contact List (configurable via `plan_required_sections`). Section matching is case-insensitive.

### dr-exercise-recent

Create a DR exercise record in `docs/dr-exercises/` named with the exercise date:

```
docs/dr-exercises/2025-11-15.md
```

```markdown
---
exercise_type: tabletop
---

# DR Exercise

## Scenario
Simulated complete loss of the primary database in us-east-1...

## Recovery Steps Tested
1. Detected outage via PagerDuty alert on error rate spike
2. Confirmed primary DB was unreachable
3. Initiated manual failover to read replica...

## Participants
- Jane Doe (Engineering Manager)
- Bob Smith (Senior SRE)

## Action Items
- [ ] Automate failover detection with custom health check
- [ ] Schedule follow-up failover exercise for Q2

## Lessons Learned
- Manual failover took 45 minutes vs. 60-minute RTO — within target
- PagerDuty alert fired within 2 minutes — alerting is solid
```

Exercise types: **tabletop** (team discussion walkthrough), **failover** (test actual failover), **full** (complete end-to-end recovery).

### dr-exercise-required-sections

Add the missing section headings to the latest exercise record. Default required sections are Scenario, Recovery Steps Tested, and Participants (configurable via `exercise_required_sections`). Section matching is case-insensitive.
