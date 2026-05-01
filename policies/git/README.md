# Git Guardrails

Enforce baselines for git-ecosystem tooling — pre-commit, gitattributes, submodules, and recent commit signatures.

## Overview

This policy enforces healthy practices for git-ecosystem tooling that lives in the repository. It covers [pre-commit](https://pre-commit.com) hook hygiene, `.gitattributes` EOL normalization, submodule pinning, and recent commit-signature coverage. Reads data from the `git` collector. Each "exists" check is universal and fails when the corresponding config is absent; dependent checks (e.g. `pre-commit-pinned-refs`) skip when no config is present so the existence check catches the absent case alone.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `pre-commit-config-exists` | Universal check — fails when no `.pre-commit-config.yaml` is present |
| `pre-commit-pinned-refs` | Every repo entry must have `rev` pinned to a non-floating ref (not `main`, `master`, `HEAD`) |
| `pre-commit-secret-scan-hook` | At least one secret-scanning hook (gitleaks, detect-secrets, trufflehog, etc.) is configured |
| `pre-commit-ci-skip-empty` | `ci.skip` is empty — no hooks are silently disabled in pre-commit.ci |
| `gitattributes-exists` | A `.gitattributes` file is present in the repository root |
| `gitattributes-eol-normalized` | `.gitattributes` declares EOL normalization (e.g. `* text=auto`) |
| `submodules-no-floating-branches` | No submodule declares a `branch` field that would make `git submodule update --remote` track a floating ref |
| `signed-commits-recent` | The last N commits on the default branch (default 50) all carry a valid GPG/SSH signature |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.git.pre_commit` | object | `git` collector (`pre-commit` sub-collector) |
| `.git.attributes` | object | `git` collector (`gitattributes` sub-collector) |
| `.git.submodules` | object | `git` collector (`gitmodules` sub-collector) |
| `.git.signing` | object | `git` collector (`signed-commits` sub-collector) |

**Note:** Ensure the `git` collector is configured before enabling this policy. Each sub-collector writes nothing when its config file is absent — this policy's existence checks rely on object presence as the signal.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/git@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [pre-commit-config-exists, gitattributes-eol-normalized]
    # with:
    #   secret_scan_hook_ids: "gitleaks,detect-secrets,trufflehog"
    #   signed_commits_window: "100"
```

## Examples

### Passing Example

A component with a pre-commit config (all repos pinned, secret scanner present, empty `ci.skip`), a `.gitattributes` with EOL normalization, no submodules tracking a floating branch, and a clean signed-commit history:

```json
{
  "git": {
    "pre_commit": {
      "valid": true,
      "repos": [
        {"repo": "https://github.com/gitleaks/gitleaks", "rev": "v8.18.0", "hooks": [{"id": "gitleaks"}]}
      ],
      "hook_ids": ["gitleaks"],
      "ci_skip": [],
      "all_pinned": true
    },
    "attributes": {
      "valid": true,
      "eol_normalized": true,
      "lfs_patterns": ["*.psd"]
    },
    "submodules": {
      "valid": true,
      "modules": [{"name": "vendor/foo", "path": "vendor/foo", "url": "https://github.com/example/foo.git", "branch": null}]
    },
    "signing": {
      "default_branch": "main",
      "commits_examined": 50,
      "signed_count": 50,
      "unsigned_count": 0,
      "all_signed": true
    }
  }
}
```

### Failing Example

A repo with floating-pinned pre-commit hooks, missing `.gitattributes`, a submodule tracking `main`, and unsigned commits in the recent history:

```json
{
  "git": {
    "pre_commit": {
      "valid": true,
      "repos": [
        {"repo": "https://github.com/pre-commit/pre-commit-hooks", "rev": "main", "hooks": [{"id": "trailing-whitespace"}]}
      ],
      "hook_ids": ["trailing-whitespace"],
      "ci_skip": ["gitleaks"],
      "all_pinned": false
    },
    "submodules": {
      "valid": true,
      "modules": [{"name": "vendor/bar", "path": "vendor/bar", "url": "https://github.com/example/bar.git", "branch": "main"}]
    },
    "signing": {
      "default_branch": "main",
      "commits_examined": 50,
      "signed_count": 35,
      "unsigned_count": 15,
      "all_signed": false
    }
  }
}
```

**Failure messages:**
- `pre-commit-pinned-refs`: `"Repo 'https://github.com/pre-commit/pre-commit-hooks' uses floating ref 'main' — pin to a tag or commit SHA"`
- `pre-commit-ci-skip-empty`: `"ci.skip disables 1 hook(s) in pre-commit.ci: gitleaks"`
- `gitattributes-exists`: `"No .gitattributes file found"`
- `submodules-no-floating-branches`: `"Submodule 'vendor/bar' tracks branch 'main' — remove the branch directive to keep the submodule pinned by SHA"`
- `signed-commits-recent`: `"15 of 50 recent commits on 'main' are unsigned"`

## Remediation

When these policies fail, you can resolve them by:

1. **`pre-commit-config-exists`** — Add a `.pre-commit-config.yaml` to the repository root. Run `pre-commit sample-config > .pre-commit-config.yaml` for a starting point.
2. **`pre-commit-pinned-refs`** — Replace floating `rev: main` with a tagged release: `rev: v4.5.0`. Run `pre-commit autoupdate` to bump every hook to its latest stable tag.
3. **`pre-commit-secret-scan-hook`** — Add a secret-scanning hook (e.g. `gitleaks`) to your config.
4. **`pre-commit-ci-skip-empty`** — Either remove entries from `ci.skip` (re-enabling enforcement in pre-commit.ci) or remove the hook from the config entirely.
5. **`gitattributes-exists`** — Add a `.gitattributes` file. A minimal one (`* text=auto`) prevents most cross-platform line-ending issues.
6. **`gitattributes-eol-normalized`** — Add `* text=auto` (or equivalent `text` / `eol=` directives) to `.gitattributes`.
7. **`submodules-no-floating-branches`** — Remove the `branch = …` line from the submodule's `.gitmodules` block. Submodules track by SHA by default; the `branch` field only matters for `git submodule update --remote`, which most repos shouldn't be using.
8. **`signed-commits-recent`** — Configure GPG or SSH signing locally (`git config commit.gpgsign true` plus a key) and require it via branch protection. Then re-sign or rebase the unsigned commits in the recent window.
