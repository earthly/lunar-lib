# Compliance Documentation Guardrails

Enforces that required compliance documentation exists, is kept current, and contains required sections.

## Overview

This policy plugin verifies that services maintain required compliance documentation. It currently covers disaster recovery exercise records — checking that DR documentation exists, exercises are conducted regularly, recovery objectives (RTO/RPO) are defined, and documents contain required sections. These policies support compliance frameworks (SOC 2, ISO 27001, NIST) that mandate documented and tested procedures.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `dr-plan-documented` | Ensures DR exercise documentation exists in the repository | No DR document found at expected path |
| `dr-exercise-recent` | Ensures a DR exercise was conducted within threshold | Last exercise is too old or no exercise date recorded |
| `dr-rto-rpo-defined` | Ensures RTO and RPO values are documented | Recovery objectives are missing from frontmatter |
| `dr-required-sections` | Ensures DR documentation contains required sections | Document is missing one or more required sections |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.oncall.disaster_recovery.plan_exists` | boolean | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.last_exercise_date` | string | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.days_since_exercise` | number | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.rto_defined` | boolean | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.rpo_defined` | boolean | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |
| `.oncall.disaster_recovery.sections` | array | [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs) collector |

**Note:** Ensure the corresponding collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/compliance-docs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [production, tier1]
    enforcement: report-pr      # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    # include: [dr-plan-documented]  # Only run specific checks (omit to run all)
    # with:
    #   max_days_since_exercise: "365"
    #   required_sections: "Scenario,Recovery Steps Tested,Participants"
```

## Examples

### Passing Example

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan_exists": true,
      "plan_path": "docs/dr-exercise.md",
      "last_exercise_date": "2025-11-15",
      "exercise_type": "tabletop",
      "days_since_exercise": 89,
      "rto_defined": true,
      "rto_minutes": 60,
      "rpo_defined": true,
      "rpo_minutes": 15,
      "last_reviewed": "2025-12-01",
      "days_since_review": 73,
      "approver": "jane.doe@company.com",
      "sections": [
        "Scenario",
        "Recovery Steps Tested",
        "Participants",
        "Action Items",
        "Lessons Learned"
      ]
    }
  }
}
```

This example passes all four policies with default configuration.

### Failing Examples

#### DR document doesn't exist (fails `dr-plan-documented`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan_exists": false
    }
  }
}
```

**Failure message:** `"DR exercise document not found (expected docs/dr-exercise.md)"`

#### DR exercise is overdue (fails `dr-exercise-recent`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan_exists": true,
      "plan_path": "docs/dr-exercise.md",
      "last_exercise_date": "2024-06-01",
      "days_since_exercise": 622,
      "sections": ["Scenario", "Recovery Steps Tested", "Participants"]
    }
  }
}
```

**Failure message:** `"Last DR exercise was 622 days ago (maximum allowed: 365)"`

#### No exercise date recorded (fails `dr-exercise-recent`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan_exists": true,
      "plan_path": "docs/dr-exercise.md",
      "rto_defined": true,
      "rto_minutes": 60,
      "sections": ["Scenario", "Recovery Steps Tested", "Participants"]
    }
  }
}
```

**Failure message:** `"No DR exercise date recorded — add last_exercise_date to frontmatter"`

#### Recovery objectives missing (fails `dr-rto-rpo-defined`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan_exists": true,
      "plan_path": "docs/dr-exercise.md",
      "rto_defined": false,
      "rpo_defined": false,
      "sections": ["Scenario", "Recovery Steps Tested", "Participants"]
    }
  }
}
```

**Failure message:** `"Recovery objectives not defined — add rto_minutes and rpo_minutes to frontmatter"`

#### Missing required sections (fails `dr-required-sections`)

```json
{
  "oncall": {
    "disaster_recovery": {
      "plan_exists": true,
      "plan_path": "docs/dr-exercise.md",
      "sections": ["Scenario"],
      "rto_defined": true,
      "rto_minutes": 60,
      "rpo_defined": true,
      "rpo_minutes": 15
    }
  }
}
```

**Failure message:** `"DR documentation is missing required sections: Recovery Steps Tested, Participants"`

## Remediation

### dr-plan-documented

Create a disaster recovery exercise document at `docs/dr-exercise.md` (or your configured path) with YAML frontmatter and Markdown body. The frontmatter captures structured metadata about the exercise, while the body documents what was tested and discussed.

Example format:

```markdown
---
last_exercise_date: 2025-11-15
exercise_type: tabletop
rto_minutes: 60
rpo_minutes: 15
last_reviewed: 2025-12-01
approver: jane.doe@company.com
---

# DR Exercise Record

## Scenario
Simulated complete loss of the primary database in us-east-1.
Assumed RDS Multi-AZ failover did not trigger automatically.

## Recovery Steps Tested
1. Detected outage via PagerDuty alert on error rate spike
2. Confirmed primary DB was unreachable
3. Initiated manual failover to read replica in us-west-2
4. Updated application config to point to new primary
5. Verified data integrity after promotion

## Participants
- Jane Doe (Engineering Manager)
- Bob Smith (Senior SRE)
- Alice Chen (Backend Lead)

## Action Items
- [ ] Automate failover detection with custom health check
- [ ] Add runbook step for verifying replication lag before promotion
- [ ] Schedule follow-up failover exercise for Q2

## Lessons Learned
- Manual failover took 45 minutes vs. 60-minute RTO — within target
- Team was unsure about replication lag threshold — needs documentation
- PagerDuty alert fired within 2 minutes — alerting is solid
```

### Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `last_exercise_date` | date | ISO 8601 date of the most recent DR exercise |
| `exercise_type` | string | Type of exercise: `tabletop`, `failover`, or `full` |
| `rto_minutes` | number | Recovery Time Objective in minutes |
| `rpo_minutes` | number | Recovery Point Objective in minutes |
| `last_reviewed` | date | ISO 8601 date of last document review |
| `approver` | string | Email of the person who approved the plan |

### dr-exercise-recent

Conduct a DR exercise and update the `last_exercise_date` and `exercise_type` fields in the frontmatter. Exercise types:
- **tabletop**: Walk through the recovery plan as a team discussion
- **failover**: Test actual failover to secondary infrastructure
- **full**: Complete end-to-end recovery simulation

### dr-rto-rpo-defined

Add `rto_minutes` and `rpo_minutes` to the YAML frontmatter:
- **RTO (Recovery Time Objective)**: Maximum acceptable time from disaster to service restoration. Example: `rto_minutes: 60` means the service must be restored within 1 hour.
- **RPO (Recovery Point Objective)**: Maximum acceptable data loss measured in time. Example: `rpo_minutes: 15` means backups/replication must ensure no more than 15 minutes of data is lost.

### dr-required-sections

Add the missing section headings to the document body. Default required sections are Scenario, Recovery Steps Tested, and Participants (configurable via the `required_sections` input). Section matching is case-insensitive.
