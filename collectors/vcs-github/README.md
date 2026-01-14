# GitHub VCS Collector

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

See the example below for the full structure.

<details>
<summary>Example Component JSON output</summary>

```json
{
  "vcs": {
    "provider": "github",
    "default_branch": "main",
    "visibility": "private",
    "topics": ["backend", "api", "microservice"],
    "merge_strategies": {
      "allow_merge_commit": true,
      "allow_squash_merge": true,
      "allow_rebase_merge": false
    },
    "branch_protection": {
      "enabled": true,
      "branch": "main",
      "require_pr": true,
      "required_approvals": 2,
      "require_codeowner_review": true,
      "dismiss_stale_reviews": true,
      "require_status_checks": true,
      "required_checks": ["ci/build", "ci/test", "security/scan"],
      "require_branches_up_to_date": true,
      "allow_force_push": false,
      "allow_deletions": false,
      "require_linear_history": false,
      "require_signed_commits": true,
      "restrictions": {
        "users": ["deployment-bot"],
        "teams": ["platform-team"],
        "apps": ["github-actions"]
      }
    },
    "access": {
      "collaborators": [
        {
          "login": "alice",
          "permission": "admin",
          "type": "User"
        },
        {
          "login": "deployment-bot",
          "permission": "write",
          "type": "Bot"
        }
      ],
      "teams": [
        {"slug": "backend-team", "name": "Backend Team", "permission": "write"},
        {"slug": "platform-team", "name": "Platform Team", "permission": "admin"}
      ]
    }
  }
}
```

</details>

## Subcollectors

This plugin includes three subcollectors:

### `basic`
Collects basic repository settings including visibility, default branch, topics, and allowed merge strategies.

### `branch-protection`
Collects branch protection rules including required approvals, status checks, force push restrictions, commit signing requirements, and push access restrictions.

### `access-permissions`
Collects repository access permissions including direct collaborators with their permission levels and teams with access to the repository. Note: Does not expand team memberships to individual users for performance reasons.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `default_branch` | No | (repository default) | Branch to check protection rules for |

## Environment Variables

This collector requires the following environment variable:

- `LUNAR_SECRET_GH_TOKEN` - GitHub personal access token with `repo` scope for API authentication
- `LUNAR_COMPONENT_ID` - Component identifier in format `github.com/owner/repo`
- `LUNAR_CI` - Must be set to `github` for the collector to run

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github.com/earthly/lunar-lib/collectors/vcs-github@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    # with:                       # Uncomment if you want to check a specific branch
    #   default_branch: "develop"
```

## Related Policies

This collector is typically used with policies that enforce:
- Branch protection is enabled with minimum required approvals
- CODEOWNER review is required
- Force push and deletions are disabled
- Required status checks are configured
- Commit signing is enforced
- Repository visibility matches organizational standards
- Required topics/tags are present

Example guardrails: `vcs-branch-protection-enabled`, `vcs-pr-min-approvals`, `vcs-codeowner-review-required`, `vcs-status-checks-required`, `vcs-no-force-push`, `vcs-signed-commits-required`, `vcs-repo-topics`, `vcs-visibility`.
