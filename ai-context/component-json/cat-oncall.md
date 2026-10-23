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

When a collector looks for the component's service and finds none, it writes `.oncall.service_lookup`, listing the places it looked. A lookup that couldn't complete (an outage, a rejected credential) goes in `errors`, so it isn't read as a missing mapping:

```json
{
  "oncall": {
    "source": { "tool": "pagerduty", "integration": "api" },
    "service_lookup": {
      "searched": ["meta:pagerduty/service-id", "input:service_id", "file:catalog-info.yaml", "component:default/checkout"],
      "errors": ["system:default/payment-platform: HTTP 503"]
    }
  }
}
```

Each collector (or sub-collector) records only what it searched, so `.oncall.service_lookup` can sit next to a `.oncall.service` that another one found; `.oncall.service.id` decides whether the component is mapped. `.oncall.source` alone doesn't mean "unmapped": the pagerduty and opsgenie collectors write it before an API call that can fail.

## Key Policy Paths

- `.oncall` — Some on-call data was collected. Not proof that on-call is configured: `dr-docs` writes `.oncall.disaster_recovery` on every component it runs on, and an unmapped component gets `.oncall.service_lookup`
- `.oncall.service.id` — Component mapped to an on-call service
- `.oncall.service_lookup` — A collector looked for a service mapping and found none (`errors`: it couldn't finish)
- `.oncall.schedule.participants` — Rotation size
- `.oncall.runbook.exists` — Runbook present
- `.oncall.sla.defined` — SLA documented
- `.oncall.disaster_recovery.plan.exists` — DR plan present
- `.oncall.disaster_recovery.plan.rto_defined` — RTO documented
- `.oncall.disaster_recovery.plan.rpo_defined` — RPO documented
- `.oncall.disaster_recovery.latest_exercise_date` — Most recent exercise date
- `.oncall.disaster_recovery.exercise_count` — Number of exercise records
