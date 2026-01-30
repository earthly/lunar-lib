# Category: `.ownership`

Code ownership and team information.

```json
{
  "ownership": {
    "codeowners": {
      "exists": true,
      "valid": true,
      "path": "CODEOWNERS",
      "errors": [],
      "has_default_rule": true,
      "owners": ["@org/platform-team", "@jdoe"]
    },
    "maintainers": ["alice@example.com", "bob@example.com"]
  }
}
```

## Key Policy Paths

- `.ownership.codeowners.exists` — CODEOWNERS file present
- `.ownership.codeowners.valid` — Syntax valid
- `.ownership.codeowners.has_default_rule` — Has catch-all rule
