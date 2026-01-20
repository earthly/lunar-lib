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
    "findings": {
      "total": 0
    },
    "issues": [],
    "clean": true
  }
}
```

## Key Policy Paths

- `.secrets` — Secret scan executed (use `assert_exists(".secrets")`)
- `.secrets.findings.total` — Secrets found
- `.secrets.clean` — No secrets detected
