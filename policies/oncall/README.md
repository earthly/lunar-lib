# On-Call Guardrails

Enforce on-call schedule, escalation, and staffing standards for production services.

## Overview

This policy validates that services have proper on-call operational readiness:
a mapping to an on-call service, an active schedule, a configured escalation
policy, and enough rotation participants to avoid burnout. It reads from the tool-agnostic `.oncall`
category, so the same guardrails work whether the data comes from PagerDuty,
OpsGenie, or another incident management tool.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `service-mapped` | Verifies the component is mapped to an on-call service |
| `schedule-configured` | Verifies an on-call schedule exists for the service |
| `escalation-defined` | Verifies an escalation policy is configured |
| `min-participants` | Ensures the rotation has enough participants (default: 2) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.oncall.service.id` | string | `pagerduty` or `opsgenie` collector (or any oncall-category collector) |
| `.oncall.unmapped` | object | `pagerduty` collector, when it looked for a service and found none |
| `.oncall.schedule.exists` | boolean | `pagerduty` or `opsgenie` collector (or any oncall-category collector) |
| `.oncall.schedule.participants` | number | `pagerduty` or `opsgenie` collector |
| `.oncall.escalation.exists` | boolean | `pagerduty` or `opsgenie` collector |

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

### Unmapped Example

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

**Failure message (`service-mapped`):** `"No PagerDuty service is mapped to this component (looked in: meta:pagerduty/service-id, input:service_id, component:default/checkout, system:default/payment-platform, file:catalog-info.yaml). Annotate its Backstage Component, System or Domain with pagerduty.com/service-id, or set the pagerduty/service-id meta or the collector's service_id input."`

`service-mapped` skips when no collector looked for a service: none is configured for the component, or its lookup couldn't complete (e.g. Backstage was unreachable). The other checks still fail on the missing data.

## Remediation

When this policy fails, you can resolve it by:

1. **service-mapped:** Map the component to its service: a `pagerduty.com/service-id` annotation on its Backstage Component (or its System or Domain, with the collector's `backstage_url` set), the `pagerduty/service-id` component meta, or the collector's `service_id` input
2. **schedule-configured:** Create an on-call schedule in your incident-management tool (PagerDuty, OpsGenie, etc.) for the service and assign team members
3. **escalation-defined:** Create an escalation policy in your incident-management tool with at least one level
4. **min-participants:** Add more team members to the on-call rotation (default minimum is 2)
