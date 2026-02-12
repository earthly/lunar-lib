# Ticket Guardrails

Enforce issue tracker ticket hygiene across your organization's pull requests. Works with any issue tracker (Jira, Linear, GitHub Issues, etc.).

## Overview

This policy verifies that PRs reference valid tickets, checks ticket status and type, enforces a specific issue tracker, and detects ticket reuse across multiple PRs. It helps teams maintain traceability between code changes and project management.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `ticket-present` | PRs must reference a ticket | No ticket ID found in PR title |
| `ticket-valid` | Referenced ticket must exist | Ticket ID was parsed but doesn't exist in the issue tracker |
| `ticket-source` | Ticket must come from an approved tracker | Ticket source not in allowed list |
| `ticket-status` | Ticket must be in an acceptable status | Ticket status is disallowed or not in allowed list |
| `ticket-type` | Ticket must be an acceptable issue type | Issue type not in allowed list |
| `ticket-reuse` | Same ticket can't be reused too many times | Ticket used in more PRs than the configured limit |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket.id` | string | Ticket ID extracted from PR title |
| `.vcs.pr.ticket.source` | string | Issue tracker name (e.g. "jira", "linear") |
| `.vcs.pr.ticket.valid` | boolean | Whether ticket exists in the tracker |
| `.vcs.pr.ticket.status` | string | Ticket workflow status |
| `.vcs.pr.ticket.type` | string | Issue type (e.g. Story, Bug) |
| `.vcs.pr.ticket.reuse_count` | number | Count of other PRs using same ticket |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/ticket
    on: ["domain:your-domain"]
    enforcement: report-pr
    with:
      allowed_sources: "jira"
      disallowed_statuses: "Done,Closed"
      max_ticket_reuse: "3"
```

## Examples

### Passing — Valid ticket with acceptable status

```json
{
  "vcs": {
    "pr": {
      "ticket": {
        "id": "ENG-456",
        "source": "jira",
        "url": "https://acme.atlassian.net/browse/ENG-456",
        "valid": true,
        "status": "In Progress",
        "type": "Story",
        "summary": "Add payment validation",
        "assignee": "jane@acme.com",
        "reuse_count": 0
      }
    }
  }
}
```

### Failing — No ticket in PR title

```json
{}
```

**Failure message:** `"PR does not reference a ticket. Include a ticket ID in the PR title (e.g. [ABC-123])."`

## Remediation

When this policy fails, you can resolve it by:

1. **ticket-present**: Add a ticket reference to your PR title (e.g. `ABC-123 Your PR description`)
2. **ticket-valid**: Verify the ticket ID exists in the issue tracker
3. **ticket-source**: Use the approved issue tracker for your organization
4. **ticket-status**: Move the ticket to an acceptable status before opening the PR
5. **ticket-type**: Use an acceptable issue type (e.g. Story, Bug, Task)
6. **ticket-reuse**: Create a new ticket for this work instead of reusing an existing one
