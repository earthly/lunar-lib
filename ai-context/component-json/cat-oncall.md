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
      "name": "Payment API",
      "discovered_via": "system:default/payment-platform"
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

`.oncall.service.discovered_via` names where the service ID came from: a meta key (`meta:pagerduty/service-id`), an input (`input:service_id`), the Backstage entity it was read from (`component:`, `system:` or `domain:<namespace>/<name>`), or a checked-out file (`file:catalog-info.yaml`).

When a collector looks for the component's service and finds none, it writes `.oncall.unmapped` in place of `.oncall.service`, listing the places it looked:

```json
{
  "oncall": {
    "source": { "tool": "pagerduty", "integration": "api" },
    "unmapped": {
      "searched": ["meta:pagerduty/service-id", "input:service_id", "component:default/checkout", "system:default/payment-platform", "file:catalog-info.yaml"]
    }
  }
}
```

A collector that couldn't complete its lookup writes neither, so an outage isn't read as a missing mapping. `.oncall.source` alone doesn't mean "unmapped": the pagerduty and opsgenie collectors write it before an API call that can fail.

## Key Policy Paths

- `.oncall` — Some on-call data was collected. Not proof that on-call is configured: `dr-docs` writes `.oncall.disaster_recovery` on every component it runs on, and an unmapped component gets `.oncall.unmapped`
- `.oncall.service.id` — Component mapped to an on-call service
- `.oncall.unmapped` — A collector looked for a service mapping and found none
- `.oncall.schedule.participants` — Rotation size
- `.oncall.runbook.exists` — Runbook present
- `.oncall.sla.defined` — SLA documented
- `.oncall.disaster_recovery.plan.exists` — DR plan present
- `.oncall.disaster_recovery.plan.rto_defined` — RTO documented
- `.oncall.disaster_recovery.plan.rpo_defined` — RPO documented
- `.oncall.disaster_recovery.latest_exercise_date` — Most recent exercise date
- `.oncall.disaster_recovery.exercise_count` — Number of exercise records
