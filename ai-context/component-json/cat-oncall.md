# Category: `.oncall`

On-call, incident management, runbooks, disaster recovery. **Normalized across PagerDuty, OpsGenie, etc.**

```json
{
  "oncall": {
    "source": {
      "tool": "pagerduty",
      "integration": "api"
    },
    "service": {
      "id": "PXXXXXX",
      "name": "Payment API"
    },
    "schedule": {
      "exists": true,
      "participants": 4,
      "rotation": "weekly"
    },
    "escalation": {
      "exists": true,
      "levels": 3
    },
    "runbook": {
      "exists": true,
      "path": "docs/runbook.md",
      "url": "https://wiki.example.com/payment-api/runbook"
    },
    "sla": {
      "defined": true,
      "response_minutes": 15,
      "uptime_percentage": 99.9
    },
    "disaster_recovery": {
      "plan": {
        "exists": true,
        "path": "docs/dr-plan.md",
        "rto_defined": true,
        "rto_minutes": 60,
        "rpo_defined": true,
        "rpo_minutes": 15,
        "last_reviewed": "2025-12-01",
        "approver": "jane@example.com",
        "sections": ["Overview", "Recovery Steps", "Contact List"]
      },
      "exercises": [
        {
          "date": "2025-11-15",
          "path": "docs/dr-exercises/2025-11-15.md",
          "exercise_type": "tabletop",
          "sections": ["Scenario", "Recovery Steps Tested", "Participants"]
        }
      ],
      "latest_exercise_date": "2025-11-15",
      "exercise_count": 1
    },
    "summary": {
      "has_oncall": true,
      "has_escalation": true,
      "has_runbook": true,
      "has_sla": true,
      "min_participants": 4
    }
  }
}
```

## Key Policy Paths

- `.oncall` — On-call configured (use `assert_exists(".oncall")`)
- `.oncall.schedule.participants` — Rotation size
- `.oncall.runbook.exists` — Runbook present
- `.oncall.sla.defined` — SLA documented
- `.oncall.disaster_recovery.plan.exists` — DR plan present
- `.oncall.disaster_recovery.plan.rto_defined` — RTO documented
- `.oncall.disaster_recovery.plan.rpo_defined` — RPO documented
- `.oncall.disaster_recovery.latest_exercise_date` — Most recent exercise date
- `.oncall.disaster_recovery.exercise_count` — Number of exercise records
