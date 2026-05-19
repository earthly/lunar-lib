# Jira Collector

Extract Jira ticket references from pull request titles and validate them against the Jira REST API.

## Overview

This collector parses PR titles for Jira ticket IDs (e.g. `[ABC-123] Fix bug`), validates the ticket against the Jira REST API, and writes normalized ticket data to `.vcs.pr.ticket` and native Jira data to `.vcs.pr.ticket.native.jira`. It also detects ticket reuse across PRs by querying the Lunar SQL database.

The normalized `.vcs.pr.ticket` paths match the Linear collector's shape, so the shared `ticket` policy works regardless of which issue tracker provided the data.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket.id` | string | Ticket key extracted from PR title (e.g. `ABC-123`) |
| `.vcs.pr.ticket.source` | object | Source metadata (`{tool: "jira", integration: "api"}`) |
| `.vcs.pr.ticket.url` | string | Direct link to the ticket on the Jira instance |
| `.vcs.pr.ticket.valid` | boolean | `true` when the Jira API returned the ticket |
| `.vcs.pr.ticket.status` | string | Ticket status name (e.g. `In Progress`) |
| `.vcs.pr.ticket.type` | string | Issue type name (e.g. `Story`, `Bug`) |
| `.vcs.pr.ticket.summary` | string | Ticket summary |
| `.vcs.pr.ticket.assignee` | string | Assignee email (subject to Atlassian email visibility — see [Required scopes](#required-scopes)) |
| `.vcs.pr.ticket.reuse_count` | number | Count of other PRs referencing the same ticket |
| `.vcs.pr.ticket.native.jira` | object | Full raw Jira API response |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `ticket` | Extracts ticket ID from PR title and fetches Jira issue metadata via the Jira REST API |
| `ticket-history` | Queries Lunar SQL for ticket reuse count across PRs (no Jira API call) |

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
- `JIRA_TOKEN` — Jira API token used as the HTTP Basic password, paired with `jira_user` as the username. See [Required scopes](#required-scopes) for the permissions this token needs.
- `GH_TOKEN` — GitHub token used to read PR titles via `GET /repos/{owner}/{repo}/pulls/{number}`. See [Required scopes](#required-scopes).

## Required scopes

The collector makes exactly two outbound API calls. The table below maps each call to the sub-collector that issues it and the minimum permission the corresponding token needs.

| Endpoint | Used by | Token | Minimum permission |
|----------|---------|-------|--------------------|
| `GET /rest/api/3/issue/{issueIdOrKey}` (Jira Cloud REST v3) | `ticket` | `JIRA_TOKEN` | `Browse Projects` on the Jira project(s) whose tickets appear in PR titles |
| `GET /repos/{owner}/{repo}/pulls/{number}` (GitHub REST) | `ticket`, `ticket-history` | `GH_TOKEN` | Read access to the PR (see breakdown below) |

The `ticket-history` sub-collector additionally queries the Lunar SQL database via `lunar sql connection-string`. That uses the platform's own credentials — no Jira or GitHub permission is involved.

### Jira token (`JIRA_TOKEN`)

The collector authenticates with HTTP Basic auth, sending `jira_user:JIRA_TOKEN` as the credential. This is the standard authentication shape for **Atlassian Cloud API tokens** (created at <https://id.atlassian.com/manage-profile/security/api-tokens>) and for **Jira Server / Data Center Personal Access Tokens (PATs)**.

API tokens and PATs operate with the same permissions as the user who created them — there are no OAuth scopes attached. The user account that owns the token needs:

- **`Browse Projects`** project permission on the Jira project(s) whose tickets are referenced in PR titles. This is the standard read-access permission and is sufficient to read `status`, `issuetype`, `summary`, and `assignee` from the issue endpoint.

No other Jira permissions are required. The collector only reads; it never writes, transitions, or comments on tickets.

#### Caveat: assignee email visibility

On Atlassian Cloud, `assignee.emailAddress` is governed by each user's email-visibility setting (Account → Profile → Contact). The field is only populated for users whose visibility is `Public` or `Anyone in your organization`; otherwise the API returns `null` and `.vcs.pr.ticket.assignee` is written as an empty string. This is an account-level Atlassian setting, **not** a token permission — granting additional scopes will not change the behavior.

#### Using OAuth 2.0 (3LO) instead of an API token

If your org disallows long-lived user tokens and you plan to mint `JIRA_TOKEN` via an Atlassian OAuth 2.0 (3LO) app, the classic scope `read:jira-work` covers `GET /rest/api/3/issue/{issueIdOrKey}` end-to-end. The granular-scope equivalents (`read:issue-meta:jira`, `read:issue:jira`, `read:status:jira`, `read:issue-type:jira`, plus `read:user:jira` for assignee email) change over time — check Atlassian's [scope reference](https://developer.atlassian.com/cloud/jira/platform/scopes-for-oauth-2-3LO-and-forge-apps/) for the current set before locking your app down.

Note: the HTTP Basic auth shape the collector uses today works with API tokens and PATs; OAuth bearer tokens would require swapping the `curl` auth method, which the collector does not currently do.

### GitHub token (`GH_TOKEN`)

The collector calls `GET /repos/{owner}/{repo}/pulls/{number}` once per PR run to read the PR title. The minimum permission depends on token type and repository visibility:

| Token type | Public repo | Private repo |
|------------|-------------|--------------|
| Classic personal access token (PAT) | No scope required | `repo` |
| Fine-grained PAT | `Metadata: Read` + `Pull requests: Read` on the target repo | `Metadata: Read` + `Pull requests: Read` on the target repo |
| GitHub App installation token | `metadata: read` + `pull_requests: read` | `metadata: read` + `pull_requests: read` |

In CI, the default `GITHUB_TOKEN` issued by GitHub Actions already satisfies these requirements for the repo running the workflow.
