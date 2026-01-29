# GitHub Collector

Collects GitHub repository settings and branch protection rules via the GitHub API.

## Overview

This collector queries the GitHub API to gather version control system (VCS) configuration data including repository visibility, default branch, topics, merge strategies, comprehensive branch protection rules, and access permissions for direct collaborators and teams. It runs on a cron schedule and requires the `LUNAR_SECRET_GH_TOKEN` environment variable for API authentication.

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

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector            | Description                                                                                                                                                      |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `repository`         | Collects basic repository settings including visibility, default branch, topics, and allowed merge strategies                                                    |
| `branch-protection`  | Collects branch protection rules including required approvals, status checks, force push restrictions, commit signing requirements, and push access restrictions |
| `access-permissions` | Collects repository access permissions including direct collaborators and teams (does not expand team memberships)                                               |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/github@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    # include: [repository]  # Only run specific checks (omit to run all)
```
