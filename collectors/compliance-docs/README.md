# Compliance Documentation Collector

Collects compliance evidence records kept in the repository, starting with penetration-test records.

## Overview

Pen-test reports are confidential and usually live outside the repository, so a team commits a short record per report instead: a Markdown file named for the report date, pointing at the report. This collector reads those records so a policy can check that the latest report is recent. It records the schedule, not the test results.

## Collected Data

The `pentest` sub-collector scans a directory (default: `docs/pentests/`) for date-named Markdown files. Only files directly in the directory whose names start with a real `YYYY-MM-DD` date count:

```
docs/pentests/
├── 2026-03-14.md
└── 2025-03-02-external.md
```

The frontmatter is optional:

```markdown
---
provider: Example Security Ltd
scope: Public API, customer web app
report_url: https://grc.example.com/reports/pentest-2026-03-14
---

# Penetration test, March 2026
```

This collector writes to the following Component JSON paths. With no records it writes an empty `reports` list, so a policy can tell a service with no records from one the collector doesn't run on.

| Path | Type | Description |
|------|------|-------------|
| `.compliance.penetration_testing.reports[]` | array | One entry per record, newest first |
| `.compliance.penetration_testing.reports[].date` | string | Report date, from the file name |
| `.compliance.penetration_testing.reports[].path` | string | Path to the record |
| `.compliance.penetration_testing.reports[].provider` | string | Who ran the test (frontmatter `provider`) |
| `.compliance.penetration_testing.reports[].scope` | string | What was tested (frontmatter `scope`; a list is joined with commas) |
| `.compliance.penetration_testing.reports[].report_url` | string | Link to the report (frontmatter `report_url`) |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|-----------|-------------|
| `pentest` | Reads date-named penetration-test records |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/compliance-docs@v1.0.0
    on: ["pentest-in-scope"]  # The services that need a pen test; pentest-report-recent skips the rest
    # with:
    #   pentest_dir_paths: "docs/pentests"
```

Disaster recovery plans and exercise records are collected by [`dr-docs`](https://github.com/earthly/lunar-lib/tree/main/collectors/dr-docs).
