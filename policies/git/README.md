# Git Guardrails

Enforce baselines for git-ecosystem tooling — pre-commit config presence, pinned hook refs, secret-scan coverage, and clean `ci.skip`.

## Overview

This policy enforces healthy practices for git-ecosystem tooling that lives in the repository. The first batch of checks targets [pre-commit](https://pre-commit.com); future additions (commitlint, gitattributes, gitmodules, signed-commits) will land as additional checks here. Reads data from the `git` collector.

`pre-commit-config-exists` is the universal check — a component opted into this policy should have a config. The other three pre-commit checks skip when no config is present, leaving `pre-commit-config-exists` to catch the absent case.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `pre-commit-config-exists` | Universal check — fails when no `.pre-commit-config.yaml` is present in the repository |
| `pre-commit-pinned-refs` | Every repo entry must have `rev` pinned to a non-floating ref (not `main`, `master`, `HEAD`) |
| `pre-commit-secret-scan-hook` | At least one secret-scanning hook (gitleaks, detect-secrets, trufflehog, etc.) is configured |
| `pre-commit-ci-skip-empty` | `ci.skip` is empty — no hooks are silently disabled in pre-commit.ci |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.git.pre_commit` | object | `git` collector |
| `.git.pre_commit.repos[]` | array | `git` collector |
| `.git.pre_commit.hook_ids` | array | `git` collector |
| `.git.pre_commit.ci_skip` | array | `git` collector |
| `.git.pre_commit.all_pinned` | boolean | `git` collector |

**Note:** Ensure the `git` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/git@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [pre-commit-config-exists, pre-commit-pinned-refs]
    # with:
    #   secret_scan_hook_ids: "gitleaks,detect-secrets,trufflehog"
```

## Examples

### Passing Example

A component with a pre-commit config, all repos pinned to tags, a secret-scanning hook, and an empty `ci.skip`:

```json
{
  "git": {
    "pre_commit": {
      "valid": true,
      "path": ".pre-commit-config.yaml",
      "repos": [
        {
          "repo": "https://github.com/pre-commit/pre-commit-hooks",
          "rev": "v4.5.0",
          "hooks": [{"id": "trailing-whitespace"}]
        },
        {
          "repo": "https://github.com/gitleaks/gitleaks",
          "rev": "v8.18.0",
          "hooks": [{"id": "gitleaks"}]
        }
      ],
      "hook_ids": ["trailing-whitespace", "gitleaks"],
      "ci_skip": [],
      "all_pinned": true
    }
  }
}
```

### Failing Example

A pre-commit config with one repo pinned to `main` and a non-empty `ci.skip` list:

```json
{
  "git": {
    "pre_commit": {
      "valid": true,
      "path": ".pre-commit-config.yaml",
      "repos": [
        {
          "repo": "https://github.com/pre-commit/pre-commit-hooks",
          "rev": "main",
          "hooks": [{"id": "trailing-whitespace"}]
        }
      ],
      "hook_ids": ["trailing-whitespace"],
      "ci_skip": ["gitleaks"],
      "all_pinned": false
    }
  }
}
```

**Failure messages:**
- `pre-commit-pinned-refs`: `"Repo 'https://github.com/pre-commit/pre-commit-hooks' uses floating ref 'main' — pin to a tag or commit SHA"`
- `pre-commit-secret-scan-hook`: `"No secret-scanning hook found. Configure at least one of: gitleaks, detect-secrets, trufflehog, detect-aws-credentials, detect-private-key"`
- `pre-commit-ci-skip-empty`: `"ci.skip disables 1 hook(s) in pre-commit.ci: gitleaks. Re-enable enforcement or remove the hook entirely."`

## Remediation

When these policies fail, you can resolve them by:

1. **`pre-commit-config-exists`** — Add a `.pre-commit-config.yaml` to the repository root. Run `pre-commit sample-config > .pre-commit-config.yaml` for a starting point.
2. **`pre-commit-pinned-refs`** — Replace floating `rev: main` (or similar) with a tagged release: `rev: v4.5.0`. Run `pre-commit autoupdate` to bump every hook to its latest stable tag.
3. **`pre-commit-secret-scan-hook`** — Add a secret-scanning hook to your config:
   ```yaml
   - repo: https://github.com/gitleaks/gitleaks
     rev: v8.18.0
     hooks:
       - id: gitleaks
   ```
4. **`pre-commit-ci-skip-empty`** — Either remove the entries from `ci.skip` (re-enabling enforcement in pre-commit.ci) or remove the hook from the config entirely. Don't keep hooks listed if you're not running them.
