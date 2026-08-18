# Ticket Adoption Guardrails

Score a component on the share of its recent pull requests that referenced a ticket.

## Overview

Change-management controls usually ask whether an individual change linked a ticket. This
guardrail asks the complementary question — whether the component links tickets *consistently* —
and it is evaluated on the default branch rather than per pull request. That placement is what
makes it count: every Lunar rollup reads default-branch state only, so per-PR ticket results
never reach an initiative score. Pair it with the per-PR `ticket` guardrails, which gate the
individual change.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `ticket-adoption` | Requires that at least `min_percentage` of the component's pull requests in the trailing window referenced a ticket | Recent changes are landing without a linked ticket often enough to fall below the threshold |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Written by | Description |
|---|---|---|
| `.vcs.ticket_adoption.percentage` | `ticket-adoption` collector | Share of pull requests in the window that referenced a ticket |
| `.vcs.ticket_adoption.prs_total` | `ticket-adoption` collector | Pull requests recorded in the window |
| `.vcs.ticket_adoption.prs_with_ticket` | `ticket-adoption` collector | How many of those carried a ticket |
| `.vcs.ticket_adoption.window_days` | `ticket-adoption` collector | Length of the trailing window, used in the failure message |

## Installation

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/ticket-adoption@main
    enforcement: score
    with:
      min_percentage: "80"
```

Scoring rather than blocking is the intended default. The metric describes a trend across many
changes, so it is a poor fit for gating any single merge — the pull request that trips the
threshold is rarely the one at fault.

## Examples

### Passing Example

```json
{
  "vcs": {
    "ticket_adoption": {
      "window_days": 30,
      "prs_total": 24,
      "prs_with_ticket": 21,
      "percentage": 87.5
    }
  }
}
```

87.5% is at or above the default 80% threshold, so the check passes.

### Failing Example

```json
{
  "vcs": {
    "ticket_adoption": {
      "window_days": 30,
      "prs_total": 20,
      "prs_with_ticket": 11,
      "percentage": 55.0
    }
  }
}
```

> Only 55.0% of PRs in the last 30d referenced a ticket (11/20); minimum is 80.0%.

## Remediation

Link a ticket on every pull request — the reference is read from the pull request title or
description by the ticket collector in use. Adding the per-PR `ticket` guardrails at
`report-pr` or `block-pr` fixes the intake, and this percentage then recovers as the trailing
window rolls forward.

Two results are deliberately *not* failures. The check skips when no adoption data has been
collected yet, and when the window contains no pull requests at all — a component that has not
changed recently has not violated a change-management control. If a component skips
persistently, its release cadence is likely longer than `window_days`; widen the window rather
than reading the skip as a gap.
