# Ticket Coverage Collector

Record what share of a component's recent pull requests referenced an issue-tracker ticket.

## Overview

Per-PR ticket checks answer "did *this* pull request link a ticket?". This collector answers
"how consistently does this component link tickets at all?" — it runs on the default branch and
asks Lunar's SQL API what fraction of the component's recent pull requests carried a resolved
ticket id. That placement is the point: every Lunar rollup reads default-branch state only, so
per-PR results never reach an initiative score, and a component with a spotless linking record
can still score zero. It reads only Lunar's own data — no issue-tracker or Git-platform API call
and no token — so it behaves the same on any Git platform.

## Collected Data

| Path | Type | Description |
|---|---|---|
| `.vcs.ticket_coverage.window_days` | number | Trailing window the metric was computed over, in days |
| `.vcs.ticket_coverage.prs_total` | number | Distinct pull requests recorded for this component in the window |
| `.vcs.ticket_coverage.prs_with_ticket` | number | How many of those carried a resolved ticket id |
| `.vcs.ticket_coverage.percentage` | number \| null | `prs_with_ticket / prs_total` as a percentage; `null` when the window holds no pull requests |

## Collectors

| Collector | Description |
|---|---|
| `ticket-coverage` | Runs on the default branch. Queries the SQL API for the component's pull requests in the trailing window and writes the coverage totals and percentage. Skips in pull-request context, when the SQL API is unreachable, or when the window holds no pull requests. |

## Installation

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/ticket-coverage@main
    with:
      window_days: "30"
```

Requires a per-PR ticket collector such as `jira` or `linear` — this aggregates the
`.vcs.pr.ticket.id` those write, so without one there is nothing to aggregate.

The window is bounded by the hub's own history: a freshly installed hub reports on the pull
requests seen since install, not the repository's full past. And a window shorter than the
component's release cadence will often be empty, in which case the metric skips rather than
reporting a misleading zero — widen `window_days` for low-traffic components.
