# VCS

Version control system (VCS) best practices and security policies for repositories

## Overview

This policy plugin enforces version control system security standards, focusing on branch protection rules that prevent unauthorized or risky changes to critical branches. Branch protection is a fundamental security control that ensures code review, testing, and approval processes are followed before changes reach production. Development teams using GitHub (or similar VCS platforms) should use this policy to enforce consistent protection rules across repositories.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `branch-protection` | Validates branch protection rules are properly configured | Branch protection is disabled or does not meet required standards |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.vcs.branch_protection.enabled` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.require_pr` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.required_approvals` | integer | `github/branch-protection` |
| `.vcs.branch_protection.require_codeowner_review` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.dismiss_stale_reviews` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.require_status_checks` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.require_branches_up_to_date` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.allow_force_push` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.allow_deletions` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.require_linear_history` | boolean | `github/branch-protection` |
| `.vcs.branch_protection.require_signed_commits` | boolean | `github/branch-protection` |

**Note:** Ensure the `github/branch-protection` collector is configured before enabling this policy.

## Inputs

All inputs are optional. If an input is not provided (left as `null`), the corresponding check is skipped. This allows you to selectively enforce only the branch protection settings that matter to your organization.

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `require_enabled` | No | `null` | Whether branch protection must be enabled (true/false) |
| `require_pr` | No | `null` | Whether pull requests are required before merging (true/false) |
| `min_approvals` | No | `null` | Minimum number of required approvals (integer) |
| `require_codeowner_review` | No | `null` | Whether code owner review is required (true/false) |
| `require_dismiss_stale_reviews` | No | `null` | Whether stale reviews must be dismissed on new commits (true/false) |
| `require_status_checks` | No | `null` | Whether status checks are required to pass (true/false) |
| `require_up_to_date` | No | `null` | Whether branches must be up to date before merging (true/false) |
| `disallow_force_push` | No | `null` | Whether force pushes should be disallowed (true/false) |
| `disallow_deletions` | No | `null` | Whether branch deletions should be disallowed (true/false) |
| `require_linear_history` | No | `null` | Whether linear history is required (true/false) |
| `require_signed_commits` | No | `null` | Whether signed commits are required (true/false) |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [production, critical]
    enforcement: report-pr       # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    with:
      require_enabled: true
      require_pr: true
      min_approvals: 1
      disallow_force_push: true
```

## Examples

### Passing Example

A repository with properly configured branch protection:

```json
{
  "vcs": {
    "branch_protection": {
      "enabled": true,
      "branch": "main",
      "require_pr": true,
      "required_approvals": 2,
      "require_codeowner_review": true,
      "dismiss_stale_reviews": true,
      "require_status_checks": true,
      "require_branches_up_to_date": true,
      "allow_force_push": false,
      "allow_deletions": false,
      "require_linear_history": false,
      "require_signed_commits": false
    }
  }
}
```

### Failing Example

A repository with branch protection disabled:

```json
{
  "vcs": {
    "branch_protection": {
      "enabled": false,
      "branch": "main"
    }
  }
}
```

**Failure message:** `"Branch protection is not enabled on main"`

Another failing example - insufficient required approvals:

```json
{
  "vcs": {
    "branch_protection": {
      "enabled": true,
      "branch": "main",
      "require_pr": true,
      "required_approvals": 0
    }
  }
}
```

**Failure message (when `min_approvals: 1`):** `"Branch protection requires 0 approval(s), but policy requires at least 1"`

## Related Collectors

This policy works with any collector that populates the required data paths. Common options include:
- `github/branch-protection` - Collects GitHub branch protection rules via GitHub API

## Remediation

When this policy fails, you can resolve it by configuring branch protection rules in your repository settings:

1. **GitHub:** Navigate to your repository → Settings → Branches → Branch protection rules
2. Select your default branch (typically `main` or `master`) or create a new rule
3. Enable the required protection settings based on the policy failures:
   - **Require pull request reviews before merging** - Set the number of required approvals
   - **Require review from Code Owners** - Enable if codeowner review is required
   - **Dismiss stale pull request approvals when new commits are pushed** - Enable if required
   - **Require status checks to pass before merging** - Enable and select required checks
   - **Require branches to be up to date before merging** - Enable if required
   - **Do not allow bypassing the above settings** - Disable "Allow force pushes" and "Allow deletions"
   - **Require linear history** - Enable if required by policy
   - **Require signed commits** - Enable if required by policy
4. Save the branch protection rule
5. Re-run the Lunar collector and policy to verify compliance
