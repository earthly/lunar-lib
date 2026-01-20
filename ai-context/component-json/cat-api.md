# Category: `.api`

API specifications.

```json
{
  "api": {
    "spec_exists": true,
    "specs": [
      {
        "type": "openapi",
        "path": "api/openapi.yaml",
        "valid": true,
        "version": "3.0.3"
      }
    ],
    "endpoints_documented": true,
    "all_secured": true
  }
}
```

## Key Policy Paths

- `.api.spec_exists` — API spec present
- `.api.specs[].valid` — Spec is valid
- `.api.all_secured` — All endpoints have auth
