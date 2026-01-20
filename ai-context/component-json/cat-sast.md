# Category: `.sast`

Static Application Security Testing. **Normalized across Semgrep, SonarQube, CodeQL, etc.**

```json
{
  "sast": {
    "source": {
      "tool": "semgrep",
      "version": "1.50.0",
      "integration": "ci"
    },
    "findings": {
      "critical": 0,
      "high": 2,
      "medium": 5,
      "low": 12,
      "total": 19
    },
    "issues": [
      {
        "severity": "high",
        "rule": "use-of-weak-crypto",
        "file": "crypto/hash.go",
        "line": 42,
        "message": "Use of weak cryptographic algorithm MD5",
        "category": "security"
      }
    ],
    "summary": {
      "has_critical": false,
      "has_high": true
    }
  }
}
```

## Key Policy Paths

- `.sast` — SAST scan executed (use `assert_exists(".sast")`)
- `.sast.findings.critical` — Critical findings
- `.sast.summary.has_critical` — Any criticals
