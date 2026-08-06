# GitLab Collector

Collects GitLab project settings, protected-branch rules, access permissions, and merge-request metadata via the GitLab API.

## Overview

This collector is the GitLab equivalent of the [`github`](../github) collector. It queries the GitLab API to gather version control system (VCS) configuration — project visibility, default branch, topics, merge method, protected-branch and approval rules, and access permissions — and, in merge-request context, the metadata of the MR being evaluated. It writes to the same `.vcs.*` schema as the GitHub collector so the shared `vcs` policy and the ticket collectors (`jira`, `linear`) work on GitLab-hosted repositories. It requires the `LUNAR_SECRET_GL_TOKEN` environment variable for API authentication, and takes an optional `gitlab_host` input (default `gitlab.com`) for self-managed instances.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.provider` | string | VCS provider name (always "gitlab") |
| `.vcs.default_branch` | string | Default branch name (e.g., "main", "master") |
| `.vcs.visibility` | string | Project visibility (public, internal, private) |
| `.vcs.topics` | array | Project topics/tags |
| `.vcs.merge_strategies` | object | Allowed merge strategies, mapped from the GitLab merge method |
| `.vcs.branch_protection` | object | Protected-branch and approval rules (`source: "gitlab"`) |
| `.vcs.access` | object | Project members and shared groups |
| `.vcs.pr` | object | Merge-request metadata (populated only in MR context) |

### Merge-request fields (`.vcs.pr`)

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.number` | number | Merge-request IID |
| `.vcs.pr.title` | string | MR title (source for ticket-ID extraction) |
| `.vcs.pr.description` | string | MR description |
| `.vcs.pr.url` | string | Web URL of the merge request |
| `.vcs.pr.source_branch` | string | Source branch name |
| `.vcs.pr.target_branch` | string | Target branch name |
| `.vcs.pr.author` | string | Author username |
| `.vcs.pr.labels` | array | MR label names |
| `.vcs.pr.draft` | boolean | Whether the MR is a draft |
| `.vcs.pr.state` | string | MR state (opened, merged, closed) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector            | Description                                                                                                                                                            |
|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `merge-request`      | Populates `.vcs.pr.*` with the metadata of the MR being evaluated (title, description, branches, author, labels, draft, state, URL). Runs only in merge-request context. This is the GitLab source of `.vcs.pr.*` that the ticket and change-management policies consume. |
| `repository`         | Collects basic project settings including visibility, default branch, topics, and the merge method mapped onto `.vcs.merge_strategies`.                               |
| `branch-protection`  | Collects protected-branch configuration and MR approval rules for the default branch, normalized into `.vcs.branch_protection` with `source: "gitlab"`.               |
| `access-permissions` | Collects project members and shared groups (does not expand group memberships).                                                                                      |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/gitlab@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    with:
      gitlab_host: gitlab.com   # Set to your self-managed host if applicable
    secrets:
      GL_TOKEN: ${{ secrets.GL_TOKEN }}
```

### `GL_TOKEN`

A GitLab personal or project access token with `read_api` scope. Used for all GitLab API calls (project settings, protected branches, approval rules, members, and merge-request metadata).

### Why `.vcs.pr.*` matters

The `jira` and `linear` ticket collectors extract a ticket ID from the merge/pull-request title to populate `.vcs.pr.ticket.*`, which the `ticket` and change-management (e.g. change→ticket) policies enforce. The `github` and `gitlab` collectors are the source of `.vcs.pr.*`: on GitLab, this collector's `merge-request` sub-collector supplies it; on GitHub, the `github` collector's `pull-request` sub-collector does. The ticket collectors' after-json variant (e.g. jira's `ticket-from-json`) then reads `.vcs.pr.title` from Component JSON — no SCM API call, provider-agnostic.

### Self-managed instances and nested namespaces

Set the `gitlab_host` input to your instance host; the API base is derived from the host prefix of the component ID. GitLab projects can live under nested groups (`group/subgroup/project`), so the full project path is URL-encoded for the API and multi-segment namespaces are handled.

### Merge-method mapping

GitLab exposes a single `merge_method` (`merge`, `rebase_merge`, `ff`) plus squash options rather than GitHub's three independent booleans. These are normalized onto `.vcs.merge_strategies.allow_merge_commit` / `allow_rebase_merge` / `allow_squash_merge` so the shared `vcs` policy applies unchanged.
