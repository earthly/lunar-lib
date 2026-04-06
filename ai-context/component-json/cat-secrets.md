# Category: `.secrets`

Secret/credential scanning. **Normalized across Gitleaks, TruffleHog, detect-secrets, etc.**

```json
{
  "secrets": {
    "source": {
      "tool": "gitleaks",
      "version": "8.18.0",
      "integration": "ci"
    },
    "issues": [
      {
        "rule": "generic-api-key",
        "file": "config/settings.py",
        "line": 42,
        "secret_type": "Generic API Key"
      }
    ]
  }
}
```

## Issue Schema

Each entry in `.secrets.issues[]` has:

| Field | Type | Description |
|-------|------|-------------|
| `rule` | string | Scanner rule ID (e.g. `generic-api-key`, `aws-access-key-id`) |
| `file` | string | Relative path to file containing the secret |
| `line` | integer | Line number of the finding |
| `secret_type` | string | Human-readable secret type |

## Key Policy Paths

- `.secrets` — Secret scan executed (use `assert_exists(".secrets")`)
- `.secrets.issues[]` — Array of detected secrets (empty = clean)
