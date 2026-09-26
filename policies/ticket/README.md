# Ticket Guardrails

Enforce issue tracker ticket hygiene across your organization's pull requests. Works with any issue tracker (Jira, Linear, GitHub Issues, etc.).

## Overview

This policy verifies that PRs reference valid tickets, checks ticket status and type, enforces a specific issue tracker, and detects ticket reuse across multiple PRs. It can also require any ticket field, such as a Jira custom field, to hold an allowed value, and run the same checks on a second reference like an architecture-review submission. It helps teams maintain traceability between code changes and project management.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `ticket-present` | PRs must reference a ticket | No ticket ID found in PR title |
| `ticket-valid` | Referenced ticket must exist | Ticket ID was parsed but the tracker did not confirm it exists |
| `ticket-source` | Ticket must come from an approved tracker | Ticket source not in allowed list |
| `ticket-status` | Ticket must be in an acceptable status | Ticket status is disallowed or not in allowed list |
| `ticket-type` | Ticket must be an acceptable issue type | Issue type not in allowed list |
| `ticket-reuse` | Same ticket can't be reused too many times | Ticket used in more PRs than the configured limit |
| `ticket-field` | A configured ticket field must have an allowed value | Field is empty or its value is not in `allowed_field_values` |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket.id` | string | Ticket ID extracted from PR title |
| `.vcs.pr.ticket.source` | string | Issue tracker name (e.g. "jira", "linear") |
| `.vcs.pr.ticket.valid` | boolean | Whether ticket exists in the tracker |
| `.vcs.pr.ticket.tracker_error` | string | Why `.valid` is absent, when the collector reports it (`not_found`, `unreachable`) |
| `.vcs.pr.ticket.status` | string | Ticket workflow status |
| `.vcs.pr.ticket.type` | string | Issue type (e.g. Story, Bug) |
| `.vcs.pr.ticket.reuse_count` | number | Count of other PRs using same ticket |
| `.vcs.pr.ticket.native` | object | Raw tracker data (e.g. `.native.jira`), read by `ticket-field` |

Every check reads from `ticket_path` instead of `.vcs.pr.ticket` when it is set.

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

### Checking a second reference

When a second jira collector import records another reference, such as an architecture-review submission at `.vcs.pr.architecture_review`, import the policy again with the same `ticket_path`. This one requires the PR to reference a submission that exists and is approved, and a custom field on it to be set:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/ticket
    name: architecture-review
    on: ["domain:your-domain"]
    enforcement: block-pr
    include: [ticket-present, ticket-valid, ticket-status, ticket-field]
    with:
      ticket_path: ".vcs.pr.architecture_review"
      allowed_statuses: "Approved"
      ticket_field: "native.jira.fields.customfield_10042"
```

`ticket_field` is relative to the ticket. A Jira select-list option matches on its `value`, a status or component on its `name`, and a user on its `displayName`; a multi-value field passes when any of its values is allowed. Jira lists custom field IDs at `GET /rest/api/3/field`.

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
7. **ticket-field**: Set the field on the ticket to one of the allowed values
