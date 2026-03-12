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
    "issues": []
  }
}
```

## Key Policy Paths

- `.secrets` — Secret scan executed (use `assert_exists(".secrets")`)
- `.secrets.issues[]` — Array of detected secrets (empty = clean)
