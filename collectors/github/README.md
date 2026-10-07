# GitHub Collector

Collects GitHub repository settings and branch protection rules via the GitHub API.

## Overview

This collector queries the GitHub API to gather version control system (VCS) configuration data including repository visibility, default branch, topics, merge strategies, branch protection rules and rulesets with their bypass actors, and access permissions for direct collaborators and teams. In PR context it also collects pull-request metadata, reviews and commit signatures (`.vcs.pr`). The opt-in `release-range` collector records, on the default branch, the commits since the previous release tag and the merged pull request behind each one. It requires the `LUNAR_SECRET_GH_TOKEN` environment variable for API authentication.

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
| `.vcs.release_range` | object | Commits since the previous release tag (opt-in, default branch only) |

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
| `.vcs.pr.head_sha` | string | Head commit of the PR |
| `.vcs.pr.reviews[]` | array | Submitted reviews, oldest first: `reviewer`, `state` (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED`), `submitted_at`, `commit_sha` |
| `.vcs.pr.commits[]` | array | The PR's commits: `sha`, `author`, `signature.verified`, `signature.reason` (GitHub's verification reason, e.g. `valid`, `unsigned`) |

Collection runs on pushes to the PR, not on review events, so `.vcs.pr.reviews` holds the reviews submitted before the last push. The approvals a PR had when it merged are recorded on the default-branch commit by `release-range`. `.vcs.pr.commits` is omitted for a PR with more than 250 commits, the most GitHub lists.

### Bypass fields (`.vcs.branch_protection`)

| Path | Type | Description |
|------|------|-------------|
| `.vcs.branch_protection.rulesets[]` | array | Every ruleset with an active rule on the default branch: `id`, `name`, `source_type`, `source`, `bypass_actors[]` (`actor_type`, `actor_id`, `bypass_mode`) |
| `.vcs.branch_protection.enforce_admins` | boolean | Classic only: administrators are held to the rules ("Do not allow bypassing the above settings") |
| `.vcs.branch_protection.bypass_pull_request_allowances` | object | Classic only: `users`, `teams` and `apps` allowed to bypass the pull-request requirement |

GitHub returns a ruleset's `bypass_actors` only to a caller with write access to that ruleset, so the key is omitted when the token cannot see it and is `[]` only when the list is empty. `actor_id` is absent for `OrganizationAdmin` and `DeployKey`.

### Release range (`.vcs.release_range`)

Written only when `release_tag_pattern` is set. The previous release is the tag matching the pattern that leaves the fewest commits ahead of it, so release tags cut on a release branch work.

| Path | Type | Description |
|------|------|-------------|
| `.vcs.release_range.tag_pattern` | string | The pattern used |
| `.vcs.release_range.head_sha` | string | The commit being evaluated |
| `.vcs.release_range.base` | object | The previous release: `tag`, `sha`. Absent when no matching tag precedes the commit |
| `.vcs.release_range.default_branch` | string | The repository's default branch |
| `.vcs.release_range.total_commits` | number | Commits in the range |
| `.vcs.release_range.truncated` | boolean | Not every commit was recorded: the range is longer than `release_range_max_commits`, or than the 1000 commits GitHub lists for a comparison |
| `.vcs.release_range.commits[]` | array | Oldest first (for a range over 1000 commits, the oldest of the newest 1000): `sha`, `author`, `signature`, and `pull_request` (`number`, `base_branch`, `head_branch`, `merged_at`, `merged_by`, `head_sha`, `approvals[]`) when GitHub associates the commit with a merged PR. A PR into the default branch is preferred; a gitflow feature commit is linked only to its PR into `develop` |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector            | Description                                                                                                                                                      |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pull-request`       | Collects pull-request metadata (`.vcs.pr`) in PR context — title, description, branches, author, labels, draft, state, URL, head SHA, reviews, and the PR's commits with signature verification. This is the GitHub source of `.vcs.pr.*` that the ticket collectors read via their after-json variants. |
| `repository`         | Collects basic repository settings including visibility, default branch, topics, and allowed merge strategies                                                    |
| `branch-protection`  | Collects branch protection rules from classic branch protection or rulesets (whichever is configured), including required approvals, status checks, force push restrictions, commit signing requirements, and push access restrictions. The `source` field on `.vcs.branch_protection` records which mechanism was detected (`"classic"`, `"ruleset"`, or `"none"`). Also lists the rulesets on the branch with their bypass actors. |
| `access-permissions` | Collects repository access permissions including direct collaborators and teams (does not expand team memberships)                                               |
| `release-range`      | Opt-in (`release_tag_pattern`). On the default branch, records the commits since the previous release tag, each with its signature verification and the merged pull request that brought it in, with that PR's approvals. |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/github@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, kubernetes]
    include:
      - pull-request        # PR metadata
      - repository          # Repository settings
      - branch-protection   # Branch protection rules
      - access-permissions  # Collaborators and teams
      - release-range       # Commits since the last release (needs release_tag_pattern)
    # with:
    #   release_tag_pattern: '^v[0-9]+\.[0-9]+\.[0-9]+$'  # enables release-range
```
