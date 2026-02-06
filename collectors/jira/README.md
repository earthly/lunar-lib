# Jira Collector

Extract Jira ticket references from pull request titles and validate them against the Jira REST API.

## Overview

This collector parses PR titles for Jira ticket IDs (e.g. `[ABC-123] Fix bug`), validates the ticket against the Jira REST API, and writes both normalized ticket data to `.vcs.pr.ticket` and native Jira data to `.jira`. It also detects ticket reuse across PRs by querying the Lunar SQL database.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket` | object | Normalized ticket reference (id, source, url, valid) |
| `.jira.ticket` | object | Normalized Jira ticket metadata (key, status, type, summary, assignee) |
| `.jira.ticket_reuse_count` | number | Count of other PRs referencing the same ticket |
| `.jira.native` | object | Full raw Jira API response |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `ticket` | Extracts ticket ID from PR title and fetches Jira issue metadata |
| `ticket-history` | Queries Lunar SQL for ticket reuse count across PRs |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/jira
    on: ["domain:your-domain"]
    with:
      jira_base_url: "https://acme.atlassian.net"
      jira_user: "user@acme.com"
```

Required secrets:
- `JIRA_TOKEN` — Jira API token
- `GH_TOKEN` — GitHub token for reading PR metadata
