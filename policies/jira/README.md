# Jira Guardrails

Enforce Jira ticket hygiene across your organization's pull requests.

## Overview

This policy verifies that PRs reference valid Jira tickets, checks ticket status and type, and detects ticket reuse across multiple PRs. It helps teams maintain traceability between code changes and project management.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `ticket-present` | PRs must reference a Jira ticket | No ticket ID found in PR title |
| `ticket-valid` | Referenced ticket must exist in Jira | Ticket ID was parsed but doesn't exist in Jira |
| `ticket-status` | Ticket must be in an acceptable status | Ticket status is disallowed or not in allowed list |
| `ticket-type` | Ticket must be an acceptable issue type | Issue type not in allowed list |
| `ticket-reuse` | Same ticket can't be reused too many times | Ticket used in more PRs than the configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.vcs.pr.ticket` | object | `jira` collector (ticket) |
| `.jira.ticket` | object | `jira` collector (ticket) |
| `.jira.ticket_reuse_count` | number | `jira` collector (ticket-history) |

**Note:** Ensure the Jira collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/jira
    on: ["domain:your-domain"]
    enforcement: report-pr
    with:
      disallowed_statuses: "Done,Closed"
      max_ticket_reuse: "3"
```

## Examples

### Passing Example

A PR with `[ENG-456] Add payment validation` in the title, where ENG-456 exists in Jira with status "In Progress":

```json
{
  "vcs": {
    "pr": {
      "ticket": {
        "id": "ENG-456",
        "source": "jira",
        "url": "https://acme.atlassian.net/browse/ENG-456",
        "valid": true
      }
    }
  },
  "jira": {
    "ticket": {
      "key": "ENG-456",
      "status": "In Progress",
      "type": "Story",
      "summary": "Add payment validation",
      "assignee": "jane@acme.com"
    },
    "ticket_reuse_count": 0
  }
}
```

### Failing Example — No Ticket

A PR with no ticket ID in the title:

```json
{}
```

**Failure message:** `"PR does not reference a Jira ticket. Include a ticket ID in the PR title (e.g. [ABC-123])."`

### Failing Example — Ticket Reuse

A ticket used in 5 other PRs (with `max_ticket_reuse: 3`):

```json
{
  "jira": {
    "ticket_reuse_count": 5
  }
}
```

**Failure message:** `"Ticket ABC-123 has been used in 5 other PRs (max allowed: 3). Create a new ticket for this work."`

## Remediation

When this policy fails, you can resolve it by:

1. **ticket-present**: Add a Jira ticket reference to your PR title (e.g. `[ABC-123] Your PR description`)
2. **ticket-valid**: Verify the ticket ID exists in Jira and the API token has access
3. **ticket-status**: Move the Jira ticket to an acceptable status before opening the PR
4. **ticket-type**: Use an acceptable issue type (e.g. Story, Bug, Task)
5. **ticket-reuse**: Create a new Jira ticket for this work instead of reusing an existing one
