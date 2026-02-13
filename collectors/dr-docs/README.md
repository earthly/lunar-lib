# DR Documentation Collector

Collects disaster recovery exercise documentation including exercise dates, RTO/RPO targets, and document structure.

## Overview

This collector parses a disaster recovery exercise document in the repository to extract structured metadata about DR readiness. It expects a Markdown file with YAML frontmatter and a Markdown body with section headings documenting what was tested and discussed. Supported frontmatter fields: `last_exercise_date` (ISO 8601 date), `exercise_type` (tabletop/failover/full), `rto_minutes`, `rpo_minutes`, `last_reviewed` (ISO 8601 date), and `approver` (email). The file path is configurable via a comma-separated candidate list with the first match winning (default: `docs/dr-exercise.md`).

## Collected Data

The collector expects a Markdown file with YAML frontmatter. Example format:

```markdown
---
last_exercise_date: 2025-11-15
exercise_type: tabletop          # tabletop, failover, full
rto_minutes: 60
rpo_minutes: 15
last_reviewed: 2025-12-01
approver: jane.doe@company.com
---

# DR Exercise Record

## Scenario
Simulated complete loss of the primary database in us-east-1...

## Recovery Steps Tested
1. Detected outage via PagerDuty alert...

## Participants
- Jane Doe (Engineering Manager)
- Bob Smith (Senior SRE)
```

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.oncall.disaster_recovery.plan_exists` | boolean | Whether a DR exercise document exists |
| `.oncall.disaster_recovery.plan_path` | string | Path to the DR document found |
| `.oncall.disaster_recovery.last_exercise_date` | string | ISO 8601 date of last DR exercise |
| `.oncall.disaster_recovery.exercise_type` | string | Type of exercise (tabletop, failover, full) |
| `.oncall.disaster_recovery.days_since_exercise` | number | Days since the last exercise |
| `.oncall.disaster_recovery.rto_defined` | boolean | Whether RTO is documented |
| `.oncall.disaster_recovery.rto_minutes` | number | Recovery Time Objective in minutes |
| `.oncall.disaster_recovery.rpo_defined` | boolean | Whether RPO is documented |
| `.oncall.disaster_recovery.rpo_minutes` | number | Recovery Point Objective in minutes |
| `.oncall.disaster_recovery.last_reviewed` | string | ISO 8601 date of last review |
| `.oncall.disaster_recovery.days_since_review` | number | Days since last review |
| `.oncall.disaster_recovery.approver` | string | Email of the plan approver |
| `.oncall.disaster_recovery.sections` | array | Section headings found in the document |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/dr-docs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, production]
    # with:
    #   path: "docs/dr-exercise.md"
```
