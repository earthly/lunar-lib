# GitHub Collector

Collects GitHub repository settings and branch protection rules via the GitHub API.

## Overview

This collector queries the GitHub API to gather version control system (VCS) configuration data including repository visibility, default branch, topics, merge strategies, comprehensive branch protection rules, and access permissions for direct collaborators and teams. In PR context it also collects pull-request metadata (`.vcs.pr`). The repository-settings collectors run on a cron schedule; the `pull-request` collector runs on PRs. It requires the `LUNAR_SECRET_GH_TOKEN` environment variable for API authentication.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.provider` | string | VCS provider name (always "github") |
| `.vcs.default_branch` | string | Default branch name (e.g., "main", "master") |
| `.vcs.visibility` | string | Repository visibility (public, private, internal) |
| `.vcs.topics` | array | Repository topics/tags |
| `.vcs.merge_strategies` | object | Allowed merge strategies for pull requests |
| `.vcs.branch_protection` | object | Branch protection rules and restrictions |
| `.vcs.access` | object | Repository access permissions for users and teams |
| `.vcs.pr` | object | Pull-request metadata (populated only in PR context) |

### Pull-request fields (`.vcs.pr`)

| Path | Type | Description |
|------|------|-------------|
| `.vcs.pr.number` | number | Pull-request number |
| `.vcs.pr.title` | string | PR title (source for ticket-ID extraction) |
| `.vcs.pr.description` | string | PR body |
| `.vcs.pr.url` | string | Web URL of the pull request |
| `.vcs.pr.source_branch` | string | Head branch name |
| `.vcs.pr.target_branch` | string | Base branch name |
| `.vcs.pr.author` | string | Author login |
| `.vcs.pr.labels` | array | PR label names |
| `.vcs.pr.draft` | boolean | Whether the PR is a draft |
| `.vcs.pr.state` | string | PR state (open, closed, merged) |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector            | Description                                                                                                                                                      |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pull-request`       | Collects pull-request metadata (`.vcs.pr`) in PR context — title, description, branches, author, labels, draft, state, URL. This is the GitHub source of `.vcs.pr.*` that the ticket collectors read via their after-json variants. |
| `repository`         | Collects basic repository settings including visibility, default branch, topics, and allowed merge strategies                                                    |
| `branch-protection`  | Collects branch protection rules from classic branch protection or rulesets (whichever is configured), including required approvals, status checks, force push restrictions, commit signing requirements, and push access restrictions. The `source` field on `.vcs.branch_protection` records which mechanism was detected (`"classic"`, `"ruleset"`, or `"none"`). |
| `access-permissions` | Collects repository access permissions including direct collaborators and teams (does not expand team memberships)                                               |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/github@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    # include: [repository]  # Only run specific checks (omit to run all)
```
