# Pre-commit Guardrails

Enforce a healthy baseline for [pre-commit](https://pre-commit.com): config exists, hooks pinned, secret scanning configured, and `ci.skip` not abused.

## Overview

Pre-commit is one of the cheapest, most effective places to enforce code-quality and credential-scanning hygiene. This policy validates the four habits that separate "we have pre-commit" from "we have pre-commit and it's actually doing something." Pair with the `pre-commit` collector, which parses `.pre-commit-config.yaml` and writes `.code_quality.pre_commit.*`.

`config-exists` is the universal check — a component opted into this policy should have a config. The other three checks (`hooks-have-pinned-refs`, `has-secret-scan-hook`, `ci-skip-empty`) skip when no config is present, leaving `config-exists` to catch the absent case. Use them together for full coverage.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `config-exists` | Universal check — fails when no `.pre-commit-config.yaml` is present in the repository |
| `hooks-have-pinned-refs` | Every repo entry must have `rev` pinned to a non-floating ref (not `main`, `master`, `HEAD`) |
| `has-secret-scan-hook` | At least one secret-scanning hook (gitleaks, detect-secrets, trufflehog, etc.) is configured |
| `ci-skip-empty` | `ci.skip` is empty — no hooks are silently disabled in pre-commit.ci |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.code_quality.pre_commit` | object | `pre-commit` collector |
| `.code_quality.pre_commit.repos[]` | array | `pre-commit` collector |
| `.code_quality.pre_commit.hook_ids` | array | `pre-commit` collector |
| `.code_quality.pre_commit.ci_skip` | array | `pre-commit` collector |
| `.code_quality.pre_commit.all_pinned` | boolean | `pre-commit` collector |

**Note:** Ensure the `pre-commit` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/pre-commit@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [config-exists, hooks-have-pinned-refs]
    # with:
    #   secret_scan_hook_ids: "gitleaks,detect-secrets,trufflehog"
```

## Examples

### Passing Example

A component with a config file, all repos pinned to tags, a secret-scanning hook, and an empty `ci.skip`:

```json
{
  "code_quality": {
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

A config with one repo pinned to `main` and a non-empty `ci.skip` list:

```json
{
  "code_quality": {
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
- `hooks-have-pinned-refs`: `"Repo 'https://github.com/pre-commit/pre-commit-hooks' uses floating ref 'main' — pin to a tag or commit SHA"`
- `has-secret-scan-hook`: `"No secret-scanning hook found. Configure at least one of: gitleaks, detect-secrets, trufflehog, detect-aws-credentials, detect-private-key"`
- `ci-skip-empty`: `"ci.skip disables 1 hook(s) in pre-commit.ci: gitleaks. Re-enable enforcement or remove the hook entirely."`

## Remediation

When these policies fail, you can resolve them by:

1. **`config-exists`** — Add a `.pre-commit-config.yaml` to the repository root. Run `pre-commit sample-config > .pre-commit-config.yaml` for a starting point.
2. **`hooks-have-pinned-refs`** — Replace floating `rev: main` (or similar) with a tagged release: `rev: v4.5.0`. Run `pre-commit autoupdate` to bump every hook to its latest stable tag.
3. **`has-secret-scan-hook`** — Add a secret-scanning hook to your config:
   ```yaml
   - repo: https://github.com/gitleaks/gitleaks
     rev: v8.18.0
     hooks:
       - id: gitleaks
   ```
4. **`ci-skip-empty`** — Either remove the entries from `ci.skip` (re-enabling enforcement in pre-commit.ci) or remove the hook from the config entirely. Don't keep hooks listed if you're not running them.
