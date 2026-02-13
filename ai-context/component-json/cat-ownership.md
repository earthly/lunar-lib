# Category: `.ownership`

Code ownership and team information.

```json
{
  "ownership": {
    "codeowners": {
      "exists": true,
      "valid": true,
      "path": ".github/CODEOWNERS",
      "errors": [],
      "owners": ["@acme/backend-team", "@acme/platform-team", "@jdoe"],
      "team_owners": ["@acme/backend-team", "@acme/platform-team"],
      "individual_owners": ["@jdoe"],
      "rules": [
        {
          "pattern": "*",
          "owners": ["@acme/platform-team"],
          "owner_count": 1,
          "line": 2
        },
        {
          "pattern": "/src/backend/",
          "owners": ["@acme/backend-team", "@jdoe"],
          "owner_count": 2,
          "line": 5
        }
      ]
    },
    "maintainers": ["alice@example.com", "bob@example.com"]
  }
}
```

## Key Policy Paths

- `.ownership.codeowners.exists` — CODEOWNERS file present
- `.ownership.codeowners.valid` — Syntax valid (no invalid owner formats)
- `.ownership.codeowners.path` — Path to the CODEOWNERS file
- `.ownership.codeowners.errors[]` — Syntax errors (`line`, `message`, `content`)
- `.ownership.codeowners.owners[]` — All unique owners across all rules
- `.ownership.codeowners.team_owners[]` — Team owners (`@org/team`)
- `.ownership.codeowners.individual_owners[]` — Individual owners (`@user`, `email`)
- `.ownership.codeowners.rules[]` — Parsed rules (`pattern`, `owners`, `owner_count`, `line`)
