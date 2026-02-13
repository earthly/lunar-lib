# CODEOWNERS Guardrails

Enforce code ownership standards via CODEOWNERS file validation

## Overview

These policies validate the CODEOWNERS file to ensure code ownership is properly defined across the repository. They check for file presence, syntax validity, catch-all coverage, owner counts, and team-based ownership. Development teams should use this policy to maintain clear ownership of every file in their repository. Requires the `codeowners` collector to be configured.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `exists` | CODEOWNERS file must be present |
| `valid` | CODEOWNERS syntax must be valid (no invalid owner formats) |
| `catchall` | Must have a default catch-all `*` rule |
| `min-owners` | Each rule must have at least N owners (configurable via `min_owners_per_rule`, default: 2) |
| `team-owners` | At least one team owner (`@org/team`) must be present |
| `no-individuals-only` | Each rule must include at least one team owner |
| `no-empty-rules` | No rules should un-assign ownership (0 owners) |
| `max-owners` | No rule should have more than N owners (configurable via `max_owners_per_rule`, default: 10) |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.ownership.codeowners.exists` | boolean | `codeowners` collector |
| `.ownership.codeowners.valid` | boolean | `codeowners` collector |
| `.ownership.codeowners.errors` | array | `codeowners` collector |
| `.ownership.codeowners.rules` | array | `codeowners` collector |
| `.ownership.codeowners.owners` | array | `codeowners` collector |
| `.ownership.codeowners.team_owners` | array | `codeowners` collector |
| `.ownership.codeowners.individual_owners` | array | `codeowners` collector |

**Note:** Ensure the `codeowners` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codeowners@v1.0.0
    on: ["domain:your-domain"]

policies:
  - uses: github://earthly/lunar-lib/policies/codeowners@v1.0.0
    on: ["domain:your-domain"]
    enforcement: report-pr
    # with:
    #   min_owners_per_rule: "2"
    #   max_owners_per_rule: "10"
```

## Examples

### Passing Example

A repository with a well-structured CODEOWNERS file:

```json
{
  "ownership": {
    "codeowners": {
      "exists": true,
      "valid": true,
      "errors": [],
      "owners": ["@acme/platform", "@acme/backend", "@jane"],
      "team_owners": ["@acme/platform", "@acme/backend"],
      "individual_owners": ["@jane"],
      "rules": [
        {"pattern": "*", "owners": ["@acme/platform", "@jane"], "owner_count": 2, "line": 2},
        {"pattern": "/src/", "owners": ["@acme/backend", "@jane"], "owner_count": 2, "line": 4}
      ]
    }
  }
}
```

**This passes** because: file exists, syntax is valid, catch-all `*` rule present, every rule has >= 2 owners, team owners are used in every rule.

### Failing Example

A repository with ownership gaps:

```json
{
  "ownership": {
    "codeowners": {
      "exists": true,
      "valid": true,
      "errors": [],
      "owners": ["@alice"],
      "team_owners": [],
      "individual_owners": ["@alice"],
      "rules": [
        {"pattern": "/src/", "owners": ["@alice"], "owner_count": 1, "line": 1}
      ]
    }
  }
}
```

**Failure messages:**
- `catchall`: "CODEOWNERS has no default catch-all rule (*). Add a '* @your-team' rule so every file has an owner."
- `team-owners`: "CODEOWNERS has no team-based owners (@org/team)."
- `min-owners`: "Rule '/src/' has 1 owner(s), minimum is 2"

## Remediation

When these policies fail, update your CODEOWNERS file:

1. **Missing file**: Create a `CODEOWNERS` file in the repository root, `.github/`, or `docs/` directory
2. **No catch-all rule**: Add a `* @your-org/your-team` line as the first rule so every file has an owner
3. **Too few owners**: Add additional owners to rules — at least 2 per rule reduces bus factor risk
4. **No team owners**: Use `@org/team-name` references instead of only individual `@username` references, so ownership survives team changes
5. **Empty rules**: Remove or add owners to rules that have no owners assigned (these un-assign ownership for matching files)
6. **Invalid syntax**: Fix owner references to use valid formats: `@user`, `@org/team`, or `email@example.com`
