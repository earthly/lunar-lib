# VCS

Version control system (VCS) best practices and security policies for repositories

## Overview

This policy plugin enforces version control system security standards, focusing on branch protection rules that prevent unauthorized or risky changes to critical branches. Branch protection is a fundamental security control that ensures code review, testing, and approval processes are followed before changes reach production. Development teams using GitHub (or similar VCS platforms) should use this policy to enforce consistent protection rules across repositories.

## Policies

This plugin provides the following policies (use `include` to select a subset):

### Branch Protection Policies

These policies enforce specific branch protection requirements. Use `include` to select which policies to enforce.

| Policy | Description |
|--------|-------------|
| `branch-protection-enabled` | Branch protection must be enabled |
| `require-pull-request` | Pull requests must be required before merging |
| `minimum-approvals` | Pull requests must have minimum number of approvals (configurable via `min_approvals` input) |
| `require-codeowner-review` | Code owner review must be required |
| `dismiss-stale-reviews` | Stale reviews must be dismissed on new commits |
| `require-status-checks` | Status checks must be required to pass |
| `require-branches-up-to-date` | Branches must be up to date before merging |
| `disallow-force-push` | Force pushes must be disallowed |
| `disallow-branch-deletion` | Branch deletions must be disallowed |
| `require-linear-history` | Linear history must be required |
| `require-signed-commits` | Signed commits must be required |

### Repository Settings Policies

| Policy | Description |
|--------|-------------|
| `require-private` | Repository visibility must be private |
| `require-default-branch` | Default branch must match required name (configurable via `required_default_branch` input, defaults to "main") |
| `allowed-merge-strategies` | Merge strategies must match allowed list (configurable via `allowed_merge_strategies` input) |

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
| `.vcs.visibility` | string | Repository visibility |
| `.vcs.default_branch` | string | Default branch name |
| `.vcs.merge_strategies.allow_merge_commit` | boolean | Whether merge commits are allowed |
| `.vcs.merge_strategies.allow_squash_merge` | boolean | Whether squash merges are allowed |
| `.vcs.merge_strategies.allow_rebase_merge` | boolean | Whether rebase merges are allowed |

**Note:** This policy requires a VCS collector (such as `github`) that populates the `.vcs` data.

## Inputs

All inputs are optional. **Exception:** `required_default_branch` defaults to `"main"`.

**Note:** Most policies have no configurable inputs. Use the `include` parameter to control which policies are enforced.

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `min_approvals` | No | `null` | Minimum number of required approvals for the `minimum-approvals` policy (integer, 0 or greater) |
| `required_default_branch` | No | `"main"` | Required default branch name for the `require-default-branch` policy |
| `allowed_merge_strategies` | No | `null` | Comma-separated list of allowed merge strategies for the `allowed-merge-strategies` policy: "merge", "squash", "rebase" (e.g., "squash,rebase") |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  # Run all policies (default - enforces all branch protection and repository settings)
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [production, critical]
    enforcement: report-pr       # Options: draft, score, report-pr, block-pr, block-release, block-pr-and-release
    with:
      min_approvals: 2
      allowed_merge_strategies: "squash"

  # Use include to run only specific policies
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    include: [
      branch-protection-enabled,
      require-pull-request,
      minimum-approvals,
      disallow-force-push,
      require-signed-commits,
      require-private
    ]
    on: ["domain:your-domain"]
    enforcement: block-pr
    with:
      min_approvals: 2

  # Run only repository settings policies
  - uses: github.com/earthly/lunar-lib/policies/vcs@v1.0.0
    include: [require-private, require-default-branch, allowed-merge-strategies]
    on: ["domain:your-domain"]
    enforcement: report-pr
    with:
      allowed_merge_strategies: "squash,rebase"
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

With policy configuration using `include` to select desired checks:
```yaml
include: [
  branch-protection-enabled,
  require-pull-request,
  minimum-approvals,
  require-codeowner-review,
  dismiss-stale-reviews,
  require-status-checks,
  require-branches-up-to-date,
  disallow-force-push,
  disallow-branch-deletion,
  require-signed-commits,
  require-private,
  require-default-branch,
  allowed-merge-strategies
]
with:
  min_approvals: 2
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

With policy configuration:
```yaml
include: [branch-protection-enabled, minimum-approvals]
with:
  min_approvals: 1
```

**Failure messages:**
- `"Branch protection is not enabled on main"`

### Failing Example - Wrong Settings

```json
{
  "vcs": {
    "visibility": "public",
    "default_branch": "master",
    "merge_strategies": {
      "allow_merge_commit": true,
      "allow_squash_merge": true,
      "allow_rebase_merge": false
    }
  }
}
```

With policy configuration:
```yaml
include: [require-private, require-default-branch, allowed-merge-strategies]
with:
  allowed_merge_strategies: "squash"
  # required_default_branch defaults to "main"
```

**Failure messages:**
- `"Repository visibility is 'public', but policy requires 'private'"`
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
     - Change visibility to match policy requirements (Private or Public)
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
