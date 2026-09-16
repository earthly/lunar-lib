# Category: `.container_scan`

Container image vulnerability scanning. **Normalized across Trivy, Grype, Clair, etc.**

```json
{
  "container_scan": {
    "source": {
      "tool": "trivy",
      "version": "0.48.0",
      "integration": "ci",
      "collected_at": "2026-07-08T03:00:12Z",
      "collected_sha": "7030ba7c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a"
    },
    "image": "gcr.io/acme/payment-api:v1.2.3",
    "digest": "sha256:de0eb0b3f2a47ba1eb89389859a9bd88b28e82f5826b6969ad604979713c2d4f",
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
       "digest": "sha256:de0eb0b3f2a47ba1eb89389859a9bd88b28e82f5826b6969ad604979713c2d4f",
       "os": {"family": "alpine", "version": "3.19"},
       "vulnerabilities": {"critical": 0, "high": 0, "medium": 2, "low": 5, "total": 7},
       "summary": {"has_critical": false, "has_high": false, "all_fixable": true}},
      {"image": "gcr.io/acme/payment-worker:v1.2.3", "tool": "trivy", "...": "..."}
    ],
    "history": [
      {"source": {"tool": "trivy", "integration": "cron", "collected_at": "2026-07-01T03:00:08Z",
                  "collected_sha": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"},
       "image": "gcr.io/acme/payment-api:v1.2.3",
       "digest": "sha256:9f2c5b1a7d3e4f60889ab0cc12de34f5678901234567890abcdef1234567890a",
       "vulnerabilities": {"critical": 1, "high": 3, "medium": 2, "low": 5, "total": 11},
       "summary": {"has_critical": true, "has_high": true, "all_fixable": false}}
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

`source.collected_at` dates the scan and `digest` names the bytes it covered.
Counts alone do not: `image` is normally a floating tag, and `vulnerabilities` is
last-writer-wins across collectors while `findings[]` is their union. A consumer
that must know the numbers describe the artifact it is promoting should compare
`digest`, not trust the count. `collected_sha` is the commit the collection ran
at, which for a cron re-scan is the latest ingested default-branch commit — not
necessarily the commit that built the image.

`history[]` is written only by the cron re-scan, only when the collector's
`container_scan_history_size` input is above `0`. Entries are oldest-first and
hold `source` / `image` / `digest` / `vulnerabilities` / `summary` — never
`findings[]`, `images[]` or `native`, which the hub concatenates. A component
running two scanners' crons has two cron records, so `history[]` is
concatenated across them like `images[]` and `findings[]`; each entry names its
scanner in `source.tool`, and each record stays within its own cap.

## Key Policy Paths

- `.container_scan` — Scan executed (use `assert_exists(".container_scan")`)
- `.container_scan.vulnerabilities.critical` — Critical vulns
- `.container_scan.summary.has_critical` — Any criticals (across every scanned image)
- `.container_scan.findings[].image` — Which image a finding was seen in
- `.container_scan.images[]` — Per-image `vulnerabilities` / `summary` / `os`
- `.container_scan.errors[]` — Pushed images the scanner could not pull or scan
- `.container_scan.digest` — Registry digest of the primary image (absent when unresolved)
- `.container_scan.source.collected_at` — When the scan ran
- `.container_scan.history[]` — Prior scans, oldest first (opt-in)
