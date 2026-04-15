# On-Call Guardrails

Enforce on-call schedule, escalation, and staffing standards for production services.

## Overview

This policy validates that services have proper on-call operational readiness:
an active schedule, a configured escalation policy, and enough rotation
participants to avoid burnout. It reads from the tool-agnostic `.oncall`
category, so the same guardrails work whether the data comes from PagerDuty,
OpsGenie, or another incident management tool.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `schedule-configured` | Verifies an on-call schedule exists for the service |
| `escalation-defined` | Verifies an escalation policy is configured |
| `min-participants` | Ensures the rotation has enough participants (default: 2) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.oncall.schedule.exists` | boolean | `pagerduty` collector (or any oncall-category collector) |
| `.oncall.schedule.participants` | number | `pagerduty` collector |
| `.oncall.escalation.exists` | boolean | `pagerduty` collector |

**Note:** Ensure a collector that writes to the `.oncall` category is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/oncall@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [schedule-configured]  # Only run specific checks
    # with:
    #   min_participants: "3"
```

## Examples

### Passing Example

```json
{
  "oncall": {
    "schedule": { "exists": true, "participants": 4, "rotation": "weekly" },
    "escalation": { "exists": true, "levels": 3 }
  }
}
```

### Failing Example

```json
{
  "oncall": {
    "schedule": { "exists": false },
    "escalation": { "exists": true, "levels": 1 }
  }
}
```

**Failure message:** `"On-call schedule is not configured for this service"`

## Remediation

When this policy fails, you can resolve it by:

1. **schedule-configured:** Create an on-call schedule in PagerDuty for the service and assign team members
2. **escalation-defined:** Create an escalation policy in PagerDuty with at least one level
3. **min-participants:** Add more team members to the on-call rotation (default minimum is 2)
