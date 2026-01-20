# Category: `.sca`

Software Composition Analysis (dependency vulnerabilities). **Normalized across Snyk, Dependabot, Semgrep, Grype, etc.**

```json
{
  "sca": {
    "source": {
      "tool": "snyk",
      "version": "1.1200.0",
      "integration": "github_app"
    },
    "vulnerabilities": {
      "critical": 0,
      "high": 1,
      "medium": 3,
      "low": 8,
      "total": 12
    },
    "findings": [
      {
        "severity": "high",
        "package": "lodash",
        "version": "4.17.19",
        "ecosystem": "npm",
        "cve": "CVE-2021-23337",
        "title": "Prototype Pollution",
        "fix_version": "4.17.21",
        "fixable": true
      }
    ],
    "summary": {
      "has_critical": false,
      "has_high": true,
      "all_fixable": true
    }
  }
}
```

## Key Policy Paths

- `.sca` — SCA scan executed (use `assert_exists(".sca")`)
- `.sca.vulnerabilities.critical` — Critical count
- `.sca.summary.has_critical` — Any criticals
- `.sca.source.tool` — Which tool (if compliance requires specific tool)

**Note:** Policies should use `assert_exists(".sca")` to verify the scanner ran, then check `.sca.vulnerabilities`. Don't check `.sca.source.tool` unless compliance mandates a specific scanner.
