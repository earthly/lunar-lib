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
| `.vcs.pr.ticket.assignee` | string | Assignee email (subject to Atlassian email visibility) |
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

| Secret | Purpose |
|--------|---------|
| `JIRA_TOKEN` | Atlassian API token used with HTTP Basic auth to read the ticket via `GET /rest/api/3/issue/{key}` |
| `GH_TOKEN` | GitHub token used to read the PR title via `GET /repos/{owner}/{repo}/pulls/{number}` |

### `JIRA_TOKEN`

Use a **classic Atlassian API token**. Steps:

1. Sign in to Atlassian as the user whose account will own the token.
2. Open <https://id.atlassian.com/manage-profile/security/api-tokens>.
3. Click **Create API token** (the plain button — *not* "Create API token with scopes").
4. Enter a label (e.g. `lunar-jira-collector`) and click **Create**.
5. Click **Copy** to copy the token, then paste it into your secret store as `JIRA_TOKEN`.
6. In Jira, make sure that same user has the **Browse Projects** permission on every project whose tickets appear in your PR titles.

Set `jira_user` to that user's Atlassian email — the collector uses HTTP Basic auth (`email:token`) against `{jira_base_url}/rest/api/3/issue/{key}`.

> **Note:** Granular ("fine-grained") Atlassian API tokens — the ones created via **Create API token with scopes** — are **not currently supported**. Atlassian's scoped tokens require a separate `api.atlassian.com/ex/jira/{cloudId}/...` gateway and Beta-state granular scopes that don't reliably grant project-level visibility in our testing. Stick with the classic token above.

`assignee.emailAddress` honors each Jira user's email-visibility setting (Account → Profile → Contact); API tokens cannot override it.

### `GH_TOKEN`

Needs read access to the PR (`GET /repos/{owner}/{repo}/pulls/{number}`).

- Classic PAT: `repo` for private repos, no scope for public
- Fine-grained PAT or GitHub App: `Metadata: Read` + `Pull requests: Read`
- GitHub Actions `GITHUB_TOKEN`: works as-is
