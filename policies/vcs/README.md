# VCS

Version control system (VCS) best practices and security policies for repositories

## Overview

This policy plugin enforces version control system security standards, focusing on branch protection rules that prevent unauthorized or risky changes to critical branches. Branch protection is a fundamental security control that ensures code review, testing, and approval processes are followed before changes reach production. Development teams using GitHub (or similar VCS platforms) should use this policy to enforce consistent protection rules across repositories.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `branch-protection` | Validates branch protection rules are properly configured | Branch protection is disabled or does not meet required standards |
| `repository-settings` | Validates repository settings including visibility, default branch, and merge strategies | Repository settings do not meet organizational standards |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.vcs.branch_protection.enabled` | boolean | Whether branch protection is enabled |
| `.vcs.branch_protection.require_pr` | boolean | Whether pull requests are required |
| `.vcs.branch_protection.required_approvals` | integer | Number of required approvals |
| `.vcs.branch_protection.require_codeowner_review` | boolean | Whether code owner review is required |
| `.vcs.branch_protection.dismiss_stale_reviews` | boolean | Whether stale reviews are dismissed |
| `.vcs.branch_protection.require_status_checks` | boolean | Whether status checks are required |
| `.vcs.branch_protection.require_branches_up_to_date` | boolean | Whether branches must be up to date |
| `.vcs.branch_protection.allow_force_push` | boolean | Whether force pushes are allowed |
| `.vcs.branch_protection.allow_deletions` | boolean | Whether branch deletions are allowed |
| `.vcs.branch_protection.require_linear_history` | boolean | Whether linear history is required |
| `.vcs.branch_protection.require_signed_commits` | boolean | Whether signed commits are required |
| `.vcs.visibility` | string | Repository visibility (public, private, internal) |
| `.vcs.default_branch` | string | Default branch name |
| `.vcs.merge_strategies.allow_merge_commit` | boolean | Whether merge commits are allowed |
| `.vcs.merge_strategies.allow_squash_merge` | boolean | Whether squash merges are allowed |
| `.vcs.merge_strategies.allow_rebase_merge` | boolean | Whether rebase merges are allowed |

**Note:** This policy requires a VCS collector (such as `github`) that populates the `.vcs` data.

## Inputs

All inputs are optional. If an input is not provided (left as `null`), the corresponding check is skipped. **Exception:** `required_default_branch` defaults to `"main"`.

**Boolean inputs support bidirectional checks:** Set `true` to require the setting be enabled, or `false` to require it be disabled.

### Branch Protection Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `require_enabled` | No | `null` | Whether branch protection must be enabled. Set `true` to require enabled, `false` to require disabled |
| `require_pr` | No | `null` | Whether pull requests are required before merging. Set `true` to require, `false` to forbid |
| `min_approvals` | No | `null` | Minimum number of required approvals (integer, 0 or greater) |
| `require_codeowner_review` | No | `null` | Whether code owner review is required. Set `true` to require, `false` to forbid |
| `require_dismiss_stale_reviews` | No | `null` | Whether stale reviews must be dismissed on new commits. Set `true` to require, `false` to forbid |
| `require_status_checks` | No | `null` | Whether status checks are required to pass. Set `true` to require, `false` to forbid |
| `require_up_to_date` | No | `null` | Whether branches must be up to date before merging. Set `true` to require, `false` to forbid |
| `disallow_force_push` | No | `null` | Whether force pushes should be disallowed. Set `true` to disallow, `false` to require allowed |
| `disallow_deletions` | No | `null` | Whether branch deletions should be disallowed. Set `true` to disallow, `false` to require allowed |
| `require_linear_history` | No | `null` | Whether linear history is required. Set `true` to require, `false` to forbid |
| `require_signed_commits` | No | `null` | Whether signed commits are required. Set `true` to require, `false` to forbid |

### Repository Settings Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `allowed_visibility` | No | `null` | Comma-separated list of allowed repository visibility levels (e.g., "private,internal"). Only listed levels are allowed |
| `required_default_branch` | No | `"main"` | Required default branch name. Defaults to requiring "main". Set to null to skip check |
| `allowed_merge_strategies` | No | `null` | Comma-separated list of allowed merge strategies: "merge", "squash", "rebase" (e.g., "squash,rebase"). Only listed strategies will be allowed (others must be disabled) |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [production, critical]
    enforcement: report-pr       # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    with:
      # Branch protection settings
      require_enabled: true
      require_pr: true
      min_approvals: 1
      disallow_force_push: true

      # Repository settings
      allowed_visibility: "private,internal"
      allowed_merge_strategies: "squash"

  # Or use include to run only specific policies
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    include: [repository-settings]
    on: ["domain:your-domain"]
    enforcement: block-pr
    with:
      allowed_visibility: "private"
      # required_default_branch defaults to "main", can be omitted
```

## Examples

### Passing Example - Production Repository

A production repository with strict security controls:

```json
{
  "vcs": {
    "provider": "github",
    "visibility": "private",
    "default_branch": "main",
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
      "require_signed_commits": true
    },
    "merge_strategies": {
      "allow_merge_commit": false,
      "allow_squash_merge": true,
      "allow_rebase_merge": false
    }
  }
}
```

With policy configuration:
```yaml
with:
  require_enabled: true
  require_pr: true
  min_approvals: 2
  require_codeowner_review: true
  disallow_force_push: true
  require_signed_commits: true
  allowed_visibility: "private"
  allowed_merge_strategies: "squash"
```

**This passes** because all security controls match policy requirements.

### Failing Example - Branch Protection Not Enabled

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

With policy requiring branch protection:
```yaml
with:
  require_enabled: true
  min_approvals: 1
```

**Failure messages:**
- `"Branch protection is not enabled on main"`

### Failing Example - Wrong Default Branch

```json
{
  "vcs": {
    "default_branch": "master",
    "merge_strategies": {
      "allow_merge_commit": true,
      "allow_squash_merge": true,
      "allow_rebase_merge": false
    }
  }
}
```

With default policy settings:
```yaml
with:
  allowed_merge_strategies: "squash"
  # required_default_branch defaults to "main"
```

**Failure messages:**
- `"Default branch is 'master', but policy requires 'main'"`
- `"Merge commits are enabled, but policy does not allow them (should be disabled)"`

## Related Collectors

These policies work with any collector that populates the required data paths. Common options include:
- `github/repository` - Collects GitHub repository settings (visibility, default branch, merge strategies)
- `github/branch-protection` - Collects GitHub branch protection rules via GitHub API

## Remediation

### Branch Protection Policy Failures

When the `branch-protection` policy fails, configure branch protection rules in your repository settings:

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

### Repository Settings Policy Failures

When the `repository-settings` policy fails, update repository settings:

1. **GitHub:** Navigate to your repository → Settings
2. Update the relevant settings based on the policy failures:
   - **Repository visibility** (General section):
     - Change visibility to match policy requirements (Private, Public, or Internal)
     - Note: Changing visibility may have security implications - consult your security team
   - **Default branch** (General section):
     - Rename your default branch if required (e.g., from `master` to `main`)
     - GitHub provides a "Rename branch" button in the repository settings
     - Update local clones and CI/CD configurations after renaming
   - **Merge button** (Pull Requests section):
     - Enable only the merge strategies listed in `allowed_merge_strategies`
     - Disable any strategies not in the allowed list
     - Example: If policy specifies `"squash,rebase"`, enable those two and disable merge commits
3. Save the changes
4. Re-run the Lunar collector and policy to verify compliance
