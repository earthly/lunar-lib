# Category: `.compliance`

Compliance and regulatory data.

```json
{
  "compliance": {
    "regimes": ["soc2", "pci-dss"],
    "data_classification": {
      "level": "confidential",
      "contains_pii": true,
      "contains_pci": true
    },
    "controls": {
      "access_reviews": true,
      "audit_logging": true,
      "encryption_at_rest": true,
      "encryption_in_transit": true
    },
    "penetration_testing": {
      "reports": [
        {
          "date": "2026-03-14",
          "path": "docs/pentests/2026-03-14.md",
          "provider": "Example Security Ltd",
          "scope": "Public API, customer web app",
          "report_url": "https://grc.example.com/reports/pentest-2026-03-14"
        }
      ]
    }
  }
}
```

`penetration_testing` holds records of penetration-test reports kept in the repository (the reports themselves usually live elsewhere). The `compliance-docs` collector writes `reports` wherever it runs, as an empty list when there are no records.

## Key Policy Paths

- `.compliance.regimes` — Applicable regimes
- `.compliance.data_classification.contains_pii` — PII flag
- `.compliance.controls.<control>` — Control status
- `.compliance.penetration_testing.reports[].date` — Pen-test report dates (freshness is computed at evaluation time)
