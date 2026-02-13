# DR Documentation Collector

Collects disaster recovery plan and exercise documentation including RTO/RPO targets, exercise history, and document structure.

## Overview

This collector parses two types of disaster recovery documentation: a DR plan and a directory of exercise records. The plan is a single Markdown file with YAML frontmatter for recovery objectives and review metadata. Exercises are date-named Markdown files (`YYYY-MM-DD.md`) in a directory, each documenting a tabletop exercise, failover test, or full recovery drill.

## Collected Data

The DR plan sub-collector expects a single file (default: `docs/dr-plan.md`):

```markdown
---
rto_minutes: 60
rpo_minutes: 15
last_reviewed: 2025-12-01
approver: jane.doe@company.com
---

# Disaster Recovery Plan

## Overview
...

## Recovery Steps
...

## Contact List
...
```

The DR exercise sub-collector scans a directory (default: `docs/dr-exercises/`) for date-named files:

```
docs/dr-exercises/
├── 2025-11-15.md    # Most recent tabletop
├── 2025-05-20.md    # Failover test
└── 2024-11-01.md    # Previous year's exercise
```

Each exercise file is a Markdown file with optional frontmatter:

```markdown
---
exercise_type: tabletop
---

# DR Exercise

## Scenario
Simulated complete loss of the primary database...

## Recovery Steps Tested
1. Detected outage via PagerDuty alert...

## Participants
- Jane Doe (Engineering Manager)
...
```

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.oncall.disaster_recovery.plan.exists` | boolean | Whether a DR plan document exists |
| `.oncall.disaster_recovery.plan.path` | string | Path to the DR plan document |
| `.oncall.disaster_recovery.plan.rto_defined` | boolean | Whether RTO is documented |
| `.oncall.disaster_recovery.plan.rto_minutes` | number | Recovery Time Objective in minutes |
| `.oncall.disaster_recovery.plan.rpo_defined` | boolean | Whether RPO is documented |
| `.oncall.disaster_recovery.plan.rpo_minutes` | number | Recovery Point Objective in minutes |
| `.oncall.disaster_recovery.plan.last_reviewed` | string | ISO 8601 date of last plan review |
| `.oncall.disaster_recovery.plan.days_since_review` | number | Days since last plan review |
| `.oncall.disaster_recovery.plan.approver` | string | Email of the plan approver |
| `.oncall.disaster_recovery.plan.sections` | array | Section headings found in the plan |
| `.oncall.disaster_recovery.exercises[]` | array | All exercise records, newest first |
| `.oncall.disaster_recovery.exercises[].date` | string | Exercise date (from filename or frontmatter) |
| `.oncall.disaster_recovery.exercises[].path` | string | Path to the exercise file |
| `.oncall.disaster_recovery.exercises[].exercise_type` | string | Type of exercise (tabletop, failover, full) |
| `.oncall.disaster_recovery.exercises[].sections` | array | Section headings found in the exercise |
| `.oncall.disaster_recovery.latest_exercise_date` | string | Date of the most recent exercise |
| `.oncall.disaster_recovery.days_since_latest_exercise` | number | Days since the most recent exercise |
| `.oncall.disaster_recovery.exercise_count` | number | Total number of exercise records |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `dr-plan` | Parses DR plan document for recovery objectives and review metadata |
| `dr-exercise` | Scans directory of date-named exercise records for exercise history |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dr-docs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, production]
    # with:
    #   plan_path: "docs/dr-plan.md"
    #   exercise_dir: "docs/dr-exercises"
```
