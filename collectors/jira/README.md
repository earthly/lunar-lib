# Jira Collector

Extract Jira ticket references from pull request titles and descriptions and validate them against the Jira REST API.

## Overview

This collector finds Jira ticket references in the PR title and description (e.g. `[ABC-123] Fix bug`, or `Fixes ABC-123` in the body), validates them against the Jira REST API and keeps the best one that exists, and writes normalized ticket data to `.vcs.pr.ticket` and native Jira data to `.vcs.pr.ticket.native.jira`. It also detects ticket reuse across PRs by querying the Lunar SQL database.

The normalized `.vcs.pr.ticket` paths match the Linear collector's shape, so the shared `ticket` policy works regardless of which issue tracker provided the data.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.ticket.id` | string | Ticket key resolved from the PR title or description (e.g. `ABC-123`) |
| `.vcs.pr.ticket.source` | object | Source metadata (`{tool: "jira", integration: "api"}`) |
| `.vcs.pr.ticket.url` | string | Direct link to the ticket on the Jira instance |
| `.vcs.pr.ticket.valid` | boolean | `true` when the Jira API returned the ticket; absent when it could not be confirmed |
| `.vcs.pr.ticket.tracker_error` | string | Why `.valid` is absent: `not_found` or `unreachable` |
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
| `ticket` | Resolves the ticket from the PR title or description and fetches its metadata via the Jira REST API |
| `ticket-history` | Queries Lunar SQL for ticket reuse count across PRs, resolving the ticket the same way `ticket` does |

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
| `GH_TOKEN` | GitHub token used to read the PR title and description via `GET /repos/{owner}/{repo}/pulls/{number}` |

### `JIRA_TOKEN`

Use a **classic Atlassian API token**. Steps:

1. Sign in to Atlassian as the user whose account will own the token.
2. Open <https://id.atlassian.com/manage-profile/security/api-tokens>.
3. Click **Create API token** (the plain button — *not* "Create API token with scopes").
4. Enter a label (e.g. `lunar-jira-collector`) and click **Create**.
5. Click **Copy** to copy the token, then paste it into your secret store as `JIRA_TOKEN`.
6. In Jira, make sure that same user has the **Browse Projects** permission on every project whose tickets appear in your PRs.

Set `jira_user` to that user's Atlassian email — the collector uses HTTP Basic auth (`email:token`) against `{jira_base_url}/rest/api/3/issue/{key}`. This is the path Atlassian themselves recommend for our shape of integration: per [Basic auth for REST APIs](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/), *"We recommend using it for simple scripts and manual calls to the REST APIs."* This collector is exactly that — a small script doing one `GET /issue/{key}` per PR.

> **Note:** Granular ("fine-grained") Atlassian API tokens — the ones created via **Create API token with scopes** — are **not currently supported**. Atlassian's scoped tokens require a separate `api.atlassian.com/ex/jira/{cloudId}/...` gateway, and even when all the right scopes are attached, Beta-state granular scopes don't reliably grant project-level visibility (verified empirically against `earthly.atlassian.net`). Atlassian's own [OAuth 2.0 scopes guidance](https://developer.atlassian.com/cloud/jira/platform/scopes-for-oauth-2-3LO-and-forge-apps/#classic-scopes) also says: *"When choosing your scopes, the recommendation is to use classic scopes"* — i.e. `read:jira-work` — rather than the granular ones. Stick with the classic API token above.

`assignee.emailAddress` honors each Jira user's email-visibility setting (Account → Profile → Contact); API tokens cannot override it.

### `GH_TOKEN`

Needs read access to the PR (`GET /repos/{owner}/{repo}/pulls/{number}`).

- Classic PAT: `repo` for private repos, no scope for public
- Fine-grained PAT or GitHub App: `Metadata: Read` + `Pull requests: Read`
- GitHub Actions `GITHUB_TOKEN`: works as-is

### Ticket resolution

Both sub-collectors build a list of candidate keys from the PR, best first, and collect the first one Jira confirms exists:

1. **Every bare reference in the PR title**, left to right — a title reference always wins.
2. **Every keyword-anchored reference in the description**, e.g. `Fixes ABC-123` or `Ticket: ABC-123`. The keywords come from `ticket_keywords` and match in either case.
3. **Every bare reference in the description**.

Step 2 outranks step 3 because a description usually names more than one ticket, and the first one to appear is often not the PR's own. Given this body, the list leads with `ENG-1234` rather than `OPS-500`:

```markdown
## Related
- Depends on OPS-500
- Reverts OPS-412

## Fixes
ENG-1234
```

A candidate Jira does not know is skipped rather than collected, so the incidental tokens a description carries — `UTF-8`, `SHA-256`, `x86-64` — cost a lookup instead of becoming the PR's ticket. `max_ticket_candidates` caps how many are tried. Only one ticket is ever collected: `.vcs.pr.ticket.id` is a single value, so the rest are dropped.

A candidate is whatever `ticket_pattern` matches. The default accepts a project key of two or more characters, so `XX-1` is collected as readily as `ABC-123`. Narrowing it to your project keys avoids the wasted lookups, and matters more when Jira validation is not configured, since then the best candidate is taken unchecked:

```yaml
with:
  ticket_pattern: "(ABC|OPS)-[0-9]+"
```

### When Jira cannot confirm the ticket

| Situation | Collected | Run |
|---|---|---|
| A candidate exists | that ticket, `.valid` true, plus status, type, summary, assignee | succeeds |
| No candidate exists in Jira | the best candidate, `.tracker_error` = `not_found` | succeeds |
| Jira unreachable after `jira_retries` | the best candidate, `.tracker_error` = `unreachable` | succeeds |
| Jira rejects the credentials | nothing | **fails** |
| Jira validation not configured | the best candidate, unchecked | succeeds |

Transient failures — connection refused, timeouts, `429`, `5xx` — are retried `jira_retries` times before the collector calls Jira unreachable. Rejected credentials are never retried: that is a misconfiguration rather than a property of the PR, so the run fails and an operator has to fix it.

The runs that succeed keep the ticket reference, so an outage does not make the PR look ticket-less — `ticket-present` still passes, and `ticket-valid` fails naming the real cause. A failed run does the opposite: the Hub discards everything the run collected, so `ticket-present` fails with "PR does not reference a ticket" until the credentials are fixed.
