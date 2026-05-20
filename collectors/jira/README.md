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
      # jira_cloud_id: "d9f4df71-…"   # required only if JIRA_TOKEN is a scoped API token
```

Required secrets:

| Secret | Purpose |
|--------|---------|
| `JIRA_TOKEN` | Atlassian API token used with HTTP Basic auth to read the ticket via `GET /rest/api/3/issue/{key}` |
| `GH_TOKEN` | GitHub token used to read the PR title via `GET /repos/{owner}/{repo}/pulls/{number}` |

### `JIRA_TOKEN`

Pick one of the two token shapes below.

**Classic API token** (recommended):

1. Open <https://id.atlassian.com/manage-profile/security/api-tokens>
2. Click **Create API token** (leave scopes empty)
3. Owner needs the `Browse Projects` permission on the relevant project(s)

**Scoped (fine-grained) API token with granular scopes**:

1. Open <https://id.atlassian.com/manage-profile/security/api-tokens>
2. Click **Create API token with scopes**
3. Grant **all** of the granular scopes that `GET /rest/api/3/issue/{key}` requires (per Atlassian's OpenAPI spec):
   - `read:issue:jira`
   - `read:issue-meta:jira`
   - `read:issue-security-level:jira`
   - `read:issue.vote:jira` (note: dot, not dash)
   - `read:issue.changelog:jira` (note: dot, not dash)
   - `read:avatar:jira`
   - `read:status:jira`
   - `read:user:jira`
   - `read:field-configuration:jira`
   - `read:email-address:jira` (optional; only needed if you want assignee email)
4. Set `jira_cloud_id` in `lunar-config.yml` (UUID from `https://<your-site>.atlassian.net/_edge/tenant_info`)

Shortcut: granting the single classic scope `read:jira-work` covers all of the above and avoids the long list.

When `jira_cloud_id` is set the collector calls `https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/issue/{key}` with `Authorization: Bearer <token>`; otherwise it calls `{jira_base_url}/rest/api/3/issue/{key}` with HTTP Basic (`email:token`).

Note: `assignee.emailAddress` honors each Jira user's email-visibility setting (Account → Profile → Contact). API tokens cannot override it; only OAuth apps with `read:email-address:jira` can.

### `GH_TOKEN`

Needs read access to the PR (`GET /repos/{owner}/{repo}/pulls/{number}`).

- Classic PAT: `repo` for private repos, no scope for public
- Fine-grained PAT or GitHub App: `Metadata: Read` + `Pull requests: Read`
- GitHub Actions `GITHUB_TOKEN`: works as-is
