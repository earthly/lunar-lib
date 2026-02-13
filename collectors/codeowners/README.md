# CODEOWNERS Collector

Parses CODEOWNERS files and collects structured code ownership data.

## Overview

This collector scans the repository for a CODEOWNERS file in standard locations (`CODEOWNERS`, `.github/CODEOWNERS`, `docs/CODEOWNERS`) and parses its contents into structured JSON. It extracts ownership rules, validates syntax, classifies owners as teams vs individuals, and detects catch-all rules. The search paths are configurable via the `paths` input.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.ownership.codeowners.exists` | boolean | Whether a CODEOWNERS file exists |
| `.ownership.codeowners.valid` | boolean | Whether the file has valid syntax (no invalid owner formats) |
| `.ownership.codeowners.path` | string | Path to the CODEOWNERS file found |
| `.ownership.codeowners.errors[]` | array | Syntax errors found (each with `line`, `message`, `content`) |
| `.ownership.codeowners.owners[]` | array | All unique owners referenced across all rules |
| `.ownership.codeowners.team_owners[]` | array | Owners that are teams (`@org/team-name`) |
| `.ownership.codeowners.individual_owners[]` | array | Owners that are individuals (`@user` or `email`) |
| `.ownership.codeowners.rules[]` | array | All parsed rules (each with `pattern`, `owners`, `owner_count`, `line`) |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codeowners@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, go]
    # with:
    #   paths: "CODEOWNERS,.github/CODEOWNERS"  # Customize search paths
```
