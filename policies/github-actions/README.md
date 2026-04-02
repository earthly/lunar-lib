# GitHub Actions Guardrails

Enforces GitHub Actions workflow lint quality and supply-chain pinning hygiene.

## Overview

This policy validates that GitHub Actions workflows are well-formed and that third-party action references follow supply-chain best practices. It checks actionlint results for syntax errors, verifies version pinning on third-party actions, and flags mutable refs that could introduce supply-chain risk.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `workflows-exist` | Repository has at least one GHA workflow defined |
| `actionlint-clean` | No actionlint errors across all workflow files |
| `actions-pinned` | All 3rd-party actions use SHA or tag pins (not branch refs) |
| `no-mutable-refs` | No 3rd-party actions reference mutable refs (`@main`, `@master`, `@latest`) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.ci.gha.workflows[]` | array | `github-actions` collector |
| `.ci.gha.actionlint` | object | `github-actions` collector |
| `.ci.gha.pinning_summary` | object | `github-actions` collector |

**Note:** Ensure the `github-actions` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/github-actions@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [actionlint-clean, actions-pinned]  # Only run specific checks
```

## Examples

### Passing Example

```json
{
  "ci": {
    "gha": {
      "workflows": [
        {
          "file": ".github/workflows/ci.yml",
          "name": "CI",
          "actions": [
            { "uses": "actions/checkout@abc123def456", "pinning": "sha", "party": "1st" },
            { "uses": "docker/build-push-action@v5.1.0", "pinning": "tag", "party": "3rd" }
          ]
        }
      ],
      "actionlint": { "errors": [], "error_count": 0, "warning_count": 0 },
      "pinning_summary": {
        "total_actions": 2,
        "sha_pinned": 1,
        "tag_pinned": 1,
        "branch_ref": 0,
        "unpinned": 0,
        "third_party_unpinned": []
      }
    }
  }
}
```

### Failing Example

```json
{
  "ci": {
    "gha": {
      "workflows": [
        {
          "file": ".github/workflows/ci.yml",
          "name": "CI",
          "actions": [
            { "uses": "docker/build-push-action@main", "pinning": "branch", "party": "3rd" }
          ]
        }
      ],
      "actionlint": {
        "errors": [{ "file": ".github/workflows/ci.yml", "line": 42, "message": "unknown field", "rule": "syntax-check" }],
        "error_count": 1,
        "warning_count": 0
      },
      "pinning_summary": {
        "total_actions": 1,
        "sha_pinned": 0,
        "tag_pinned": 0,
        "branch_ref": 1,
        "unpinned": 0,
        "third_party_unpinned": ["docker/build-push-action@main"]
      }
    }
  }
}
```

**Failure messages:**
- `actionlint-clean`: "1 actionlint error(s) found across workflow files"
- `actions-pinned`: "1 third-party action(s) not pinned to SHA or tag: docker/build-push-action@main"
- `no-mutable-refs`: "1 third-party action(s) using mutable refs: docker/build-push-action@main"

## Remediation

When this policy fails, you can resolve it by:

1. **`workflows-exist` failure:** Add at least one GitHub Actions workflow to `.github/workflows/`.
2. **`actionlint-clean` failure:** Fix the reported lint errors. Run `actionlint` locally to see all issues with file and line references.
3. **`actions-pinned` failure:** Pin third-party actions to a SHA (`@abc123...`) or a specific tag (`@v4.1.0`) instead of using branch refs.
4. **`no-mutable-refs` failure:** Replace mutable refs like `@main`, `@master`, or `@latest` with immutable SHA or tag references.
