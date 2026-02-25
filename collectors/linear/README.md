# `linear` Collector

Extract Linear ticket references from pull request titles and validate them against the Linear GraphQL API.

## Overview

This collector parses PR titles for Linear ticket IDs (e.g. `[ENG-123] Fix bug`), validates the ticket against the Linear GraphQL API, and writes both normalized ticket data to `.vcs.pr.ticket` and native Linear data to `.vcs.pr.ticket.native.linear`. It also detects ticket reuse across PRs by querying the Lunar SQL database.

The normalized `.vcs.pr.ticket` paths are the same as the Jira collector, so the existing `ticket` policy works with both issue trackers without any changes.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket` | object | Normalized ticket reference (id, source, url, valid, status, type, summary, assignee) |
| `.vcs.pr.ticket.reuse_count` | number | Count of other PRs referencing the same ticket |
| `.vcs.pr.ticket.native.linear` | object | Full raw Linear GraphQL response |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `ticket` | Extracts ticket ID from PR title and fetches Linear issue metadata |
| `ticket-history` | Queries Lunar SQL for ticket reuse count across PRs |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/linear
    on: ["domain:your-domain"]
    with:
      type_labels: "bug,feature,chore,improvement"
```

Required secrets:
- `LINEAR_API_KEY` — Linear personal API key (Settings → API → Personal API keys)
- `GH_TOKEN` — GitHub token for reading PR metadata

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `ticket_prefix` | `""` | Character(s) before the ticket ID in PR titles |
| `ticket_suffix` | `""` | Character(s) after the ticket ID in PR titles |
| `ticket_pattern` | `[A-Za-z][A-Za-z0-9]+-[0-9]+` | Regex pattern for ticket ID |
| `type_labels` | `""` | Comma-separated label names to treat as issue types |

## Notes

- **Issue types:** Linear has no native "issue type" field. The `type_labels` input lets you specify label names (e.g. `bug,feature,chore`) that should be treated as types. If a matching label is found on the issue, it is written to `.vcs.pr.ticket.type`.
- **Ticket URL:** The Linear GraphQL API returns the full issue URL, so no base URL input is needed (unlike the Jira collector).
- **Ticket ID format:** Linear uses `TEAM-NUMBER` identifiers (e.g. `ENG-123`), which match the same default regex as Jira.
