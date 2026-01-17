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

| Path | Type |
|------|------|
| `.vcs.branch_protection.enabled` | boolean |
| `.vcs.branch_protection.require_pr` | boolean |
| `.vcs.branch_protection.required_approvals` | integer |
| `.vcs.branch_protection.require_codeowner_review` | boolean |
| `.vcs.branch_protection.dismiss_stale_reviews` | boolean |
| `.vcs.branch_protection.require_status_checks` | boolean |
| `.vcs.branch_protection.require_branches_up_to_date` | boolean |
| `.vcs.branch_protection.allow_force_push` | boolean |
| `.vcs.branch_protection.allow_deletions` | boolean |
| `.vcs.branch_protection.require_linear_history` | boolean |
| `.vcs.branch_protection.require_signed_commits` | boolean |

**Note:** This policy requires a VCS collector (such as `github`) that populates the `.vcs.branch_protection` data.

---

## Policy: `repository-settings`

### Required Data

This policy reads from the following Component JSON paths:

| Path | Type |
|------|------|
| `.vcs.visibility` | string |
| `.vcs.default_branch` | string |
| `.vcs.merge_strategies.allow_merge_commit` | boolean |
| `.vcs.merge_strategies.allow_squash_merge` | boolean |
| `.vcs.merge_strategies.allow_rebase_merge` | boolean |

**Note:** This policy requires a VCS collector (such as `github/repository`) that populates the `.vcs` repository data.

### Inputs

All inputs are optional. If an input is not provided (left as `null`), the corresponding check is skipped.

**Boolean inputs support bidirectional checks:** Set `true` to require the setting be enabled, or `false` to require it be disabled.

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `allowed_visibility` | No | `null` | Comma-separated list of allowed repository visibility levels (e.g., "private,internal") |
| `required_default_branch` | No | `null` | Required default branch name (e.g., "main") |
| `allow_merge_commit` | No | `null` | Whether merge commits should be allowed. Set `true` to require enabled, `false` to require disabled |
| `allow_squash_merge` | No | `null` | Whether squash merges should be allowed. Set `true` to require enabled, `false` to require disabled |
| `allow_rebase_merge` | No | `null` | Whether rebase merges should be allowed. Set `true` to require enabled, `false` to require disabled |

### Examples

#### Passing Example - Private repository with main branch

```json
{
  "vcs": {
    "provider": "github",
    "visibility": "private",
    "default_branch": "main",
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
  allowed_visibility: "private,internal"
  required_default_branch: "main"
  allow_squash_merge: true
  allow_merge_commit: false
  allow_rebase_merge: false
```

#### Failing Example - Public repository when only private allowed

```json
{
  "vcs": {
    "visibility": "public",
    "default_branch": "main"
  }
}
```

**Failure message (when `allowed_visibility: "private"`):** `"Repository visibility 'public' is not in allowed list: private"`

#### Failing Example - Wrong default branch

```json
{
  "vcs": {
    "visibility": "private",
    "default_branch": "master"
  }
}
```

**Failure message (when `required_default_branch: "main"`):** `"Default branch is 'master', but policy requires 'main'"`

#### Failing Example - Merge commits enabled when should be disabled

```json
{
  "vcs": {
    "merge_strategies": {
      "allow_merge_commit": true,
      "allow_squash_merge": true,
      "allow_rebase_merge": false
    }
  }
}
```

**Failure message (when `allow_merge_commit: false`):** `"Merge commits are allowed, but policy requires them to be disabled"`

#### Bidirectional Example - Require Merge Commits Enabled

Some teams prefer merge commits over squash for better git history:

```json
{
  "vcs": {
    "merge_strategies": {
      "allow_merge_commit": false,
      "allow_squash_merge": true,
      "allow_rebase_merge": false
    }
  }
}
```

With policy requiring merge commits:
```yaml
with:
  allow_merge_commit: true  # Require merge commits enabled
```

**Failure message:** `"Merge commits are disabled, but policy requires them to be allowed"`

---

## Inputs

All inputs are optional. If an input is not provided (left as `null`), the corresponding check is skipped. This allows you to selectively enforce only the branch protection settings that matter to your organization.

**Boolean inputs support bidirectional checks:** Set `true` to require the setting be enabled, or `false` to require it be disabled.

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
      required_default_branch: "main"
      allow_squash_merge: true
      allow_merge_commit: false

  # Or use include to run only specific policies
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    include: [repository-settings]
    on: ["domain:your-domain"]
    enforcement: block-pr
    with:
      allowed_visibility: "private"
      required_default_branch: "main"
```

## Examples

### Passing Example - Strict Branch Protection

A production repository with strict branch protection enabled:

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

### Passing Example - Relaxed Settings for Internal Tools

A test or internal tool repository where restrictions should be minimal:

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

With policy configuration verifying no excessive restrictions:
```yaml
with:
  require_enabled: false          # Verify branch protection is disabled
  require_signed_commits: false   # Verify signed commits are not required
```

**This passes** because branch protection is disabled as required.

### Bidirectional Check Example - Status Checks

Verifying status checks are NOT required (useful for personal projects):

```json
{
  "vcs": {
    "branch_protection": {
      "enabled": true,
      "require_status_checks": true
    }
  }
}
```

**Failure message (when `require_status_checks: false`):** `"Branch protection requires status checks, but policy requires them to not be required"`

## Related Collectors

These policies work with any collector that populates the required data paths. Common options include:
- `github/repository` - Collects GitHub repository settings (visibility, default branch, merge strategies)
- `github/branch-protection` - Collects GitHub branch protection rules via GitHub API

## Remediation

### Branch Protection Policy Failures

When the `branch-protection` policy fails, you can resolve it by configuring branch protection rules in your repository settings:

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

When the `repository-settings` policy fails, you can resolve it by updating repository settings:

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
     - Enable/disable "Allow merge commits" based on policy
     - Enable/disable "Allow squash merging" based on policy
     - Enable/disable "Allow rebase merging" based on policy
3. Save the changes
4. Re-run the Lunar collector and policy to verify compliance
