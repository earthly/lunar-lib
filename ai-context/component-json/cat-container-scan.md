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
    },
    "findings": [
      {"severity": "medium", "package": "libssl3", "version": "3.1.4-r5", "ecosystem": "apk",
       "cve": "CVE-2024-0001", "fix_version": "3.1.4-r6", "fixable": true,
       "image": "gcr.io/acme/payment-api:v1.2.3"}
    ],
    "images": [
      {"image": "gcr.io/acme/payment-api:v1.2.3", "tool": "trivy",
       "os": {"family": "alpine", "version": "3.19"},
       "vulnerabilities": {"critical": 0, "high": 0, "medium": 2, "low": 5, "total": 7},
       "summary": {"has_critical": false, "has_high": false, "all_fixable": true}},
      {"image": "gcr.io/acme/payment-worker:v1.2.3", "tool": "trivy", "...": "..."}
    ],
    "errors": [
      {"image": "gcr.io/acme/payment-migrate:v1.2.3", "error": "failed to pull image: unauthorized"}
    ]
  }
}
```

A component that pushes several images gets one `.container_scan`: `image` / `os` /
`native.*` describe the **primary** (most recently pushed) image, `vulnerabilities` /
`summary` / `findings[]` span **every** scanned image, `images[]` is the per-image
breakdown, and `errors[]` lists pushed images that could not be scanned. `images[]`
and `findings[]` from two scanners (trivy + grype) are concatenated by the hub — tell
them apart by `tool`.

## Key Policy Paths

- `.container_scan` — Scan executed (use `assert_exists(".container_scan")`)
- `.container_scan.vulnerabilities.critical` — Critical vulns
- `.container_scan.summary.has_critical` — Any criticals (across every scanned image)
- `.container_scan.findings[].image` — Which image a finding was seen in
- `.container_scan.images[]` — Per-image `vulnerabilities` / `summary` / `os`
- `.container_scan.errors[]` — Pushed images the scanner could not pull or scan
