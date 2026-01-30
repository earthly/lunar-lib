# Category: `.container_scan`

Container image vulnerability scanning. **Normalized across Trivy, Grype, Clair, etc.**

```json
{
  "container_scan": {
    "source": {
      "tool": "trivy",
      "version": "0.48.0",
      "integration": "ci"
    },
    "image": "gcr.io/acme/payment-api:v1.2.3",
    "vulnerabilities": {
      "critical": 0,
      "high": 0,
      "medium": 2,
      "low": 5,
      "total": 7
    },
    "os": {
      "family": "alpine",
      "version": "3.19"
    },
    "summary": {
      "has_critical": false,
      "has_high": false
    }
  }
}
```

## Key Policy Paths

- `.container_scan` — Scan executed (use `assert_exists(".container_scan")`)
- `.container_scan.vulnerabilities.critical` — Critical vulns
- `.container_scan.summary.has_critical` — Any criticals
