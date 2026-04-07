# CI Guardrails

Enforces CI configuration lint quality and supply-chain dependency pinning.

## Overview

This policy validates that CI configurations are well-formed and that third-party CI dependencies follow supply-chain best practices. It reads from normalized Component JSON paths (`.ci.lint`, `.ci.dependencies`), so it works regardless of which CI vendor collector populated the data — GitHub Actions, GitLab CI, CircleCI, etc.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `lint-clean` | No lint errors across CI configuration files |
| `dependencies-pinned` | All 3rd-party CI dependencies use SHA or tag pins (not branch refs) |
| `no-mutable-refs` | No 3rd-party CI dependencies reference mutable refs (`@main`, `@master`, `@latest`) |

## Required Data

This policy reads from **normalized** (vendor-agnostic) Component JSON paths only:

| Path | Type | Provided By |
|------|------|-------------|
| `.ci.lint` | object | Any CI collector (e.g. `github-actions`) |
| `.ci.dependencies` | object | Any CI collector (e.g. `github-actions`) |

**Note:** At least one CI collector must be configured to populate these normalized paths.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/ci@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [lint-clean, dependencies-pinned]  # Only run specific checks
```

## Examples

### Passing Example

```json
{
  "ci": {
    "lint": {
      "errors": [],
      "error_count": 0,
      "warning_count": 0
    },
    "dependencies": {
      "total": 2,
      "pinned": 2,
      "unpinned": 0,
      "items": [
        { "name": "actions/checkout", "ref": "abc123def456", "pinning": "sha", "party": "1st" },
        { "name": "docker/build-push-action", "ref": "v5.1.0", "pinning": "tag", "party": "3rd" }
      ],
      "third_party_unpinned": []
    }
  }
}
```

### Failing Example

```json
{
  "ci": {
    "lint": {
      "errors": [{ "file": ".github/workflows/ci.yml", "line": 42, "message": "unknown field", "rule": "syntax-check" }],
      "error_count": 1,
      "warning_count": 0
    },
    "dependencies": {
      "total": 1,
      "pinned": 0,
      "unpinned": 1,
      "items": [
        { "name": "docker/build-push-action", "ref": "main", "pinning": "branch", "party": "3rd" }
      ],
      "third_party_unpinned": ["docker/build-push-action@main"]
    }
  }
}
```

**Failure messages:**
- `lint-clean`: "1 lint error(s) found across CI configuration files"
- `dependencies-pinned`: "1 third-party CI dependency(ies) not pinned to SHA or tag: docker/build-push-action@main"
- `no-mutable-refs`: "1 third-party CI dependency(ies) using mutable refs: docker/build-push-action@main"

## Remediation

When this policy fails, you can resolve it by:

1. **`lint-clean` failure:** Fix the reported lint errors. Run your CI vendor's linter locally (e.g. `actionlint` for GHA, `gitlab-ci-lint` for GitLab) to see all issues with file and line references.
2. **`dependencies-pinned` failure:** Pin third-party CI dependencies to a SHA (`@abc123...`) or a specific tag (`@v4.1.0`) instead of using branch refs.
3. **`no-mutable-refs` failure:** Replace mutable refs like `@main`, `@master`, or `@latest` with immutable SHA or tag references.
