# SonarQube Collector

Collect quality gate status, ratings, and code quality metrics from the
SonarQube or SonarCloud Web API.

## Overview

This collector queries the SonarQube/SonarCloud Web API on a daily cron
schedule to gather quality gate status, ratings, and key metrics (bugs,
vulnerabilities, code smells, coverage, duplication). The project key is
resolved from the component's `sonarqube/project-key` meta annotation or the
`project_key` input.

Results are written to the `.code_quality` category in a tool-agnostic format,
so a future `code-quality` policy can evaluate the same paths regardless of
which scanner produced the data. The same collector works against both
SonarQube (self-hosted) and SonarCloud — only the `sonarqube_base_url` input
differs.

## Collected Data

This collector writes to the following Component JSON paths. The top-level
`.code_quality.*` fields are **tool-agnostic** and intended for a generic
code-quality policy. SonarQube-specific structure (the rating split, quality
gate detail, SQALE debt, native metric names) lives under
`.code_quality.native.sonarqube` for SonarQube-aware policies.

| Path | Type | Description |
|------|------|-------------|
| `.code_quality.source` | object | Tool, integration, project key, and API URL |
| `.code_quality.passing` | bool | Overall pass/fail signal — derived from SonarQube's quality gate status |
| `.code_quality.coverage_percentage` | number | Line coverage percentage (0–100), if measured |
| `.code_quality.duplication_percentage` | number | Duplicated lines percentage (0–100), if measured |
| `.code_quality.issue_counts` | object | Severity buckets: `total`, `critical`, `high`, `medium`, `low` (same shape as `.sca` / `.sast`) |
| `.code_quality.native.sonarqube` | object | Raw SonarQube/SonarCloud API responses: quality gate detail, reliability/security/maintainability rating split, SQALE debt, native metric names |

## Collectors

This integration provides the following collectors:

| Collector | Description |
|-----------|-------------|
| `api` | Queries the SonarQube/SonarCloud Web API for quality gate status and metrics, writes a tool-agnostic summary at `.code_quality.*` with raw responses under `.code_quality.native.sonarqube` |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/sonarqube@v1.0.0
    on: ["domain:your-domain"]
    # with:
    #   project_key: "my-org_my-service"        # Optional — falls back to catalog meta annotation
    #   sonarqube_base_url: "https://sonarcloud.io"  # Or your self-hosted SonarQube URL
```

Required secrets:
- `SONARQUBE_TOKEN` — SonarQube/SonarCloud user token with `Browse` permission on the target project. Sent as the HTTP Basic username with an empty password (per the SonarQube Web API convention).

### Project key discovery

The collector resolves the SonarQube project key in this order:

1. **Catalog meta annotation** — reads `sonarqube/project-key` from the component's lunar catalog meta. Set via `lunar catalog component --meta sonarqube/project-key <key>`, typically invoked by a company-specific cataloger that knows which components map to which SonarQube projects. This is the recommended approach for orgs where each component has its own project.
2. **Explicit `project_key` input** — set in `lunar-config.yml` for static cases, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own project).
3. **Neither found** — the collector exits cleanly with no data written.

### SonarQube vs SonarCloud

Both SonarQube (self-hosted) and SonarCloud expose the same Web API. Select
the instance by overriding `sonarqube_base_url`:

| Instance | `sonarqube_base_url` |
|----------|----------------------|
| SonarCloud (default) | `https://sonarcloud.io` |
| SonarQube self-hosted | e.g. `https://sonar.example.com` |

Tokens are created the same way on both — in the user profile under **Security → Generate Tokens**.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `project_key` | *(empty — falls back to catalog meta)* | SonarQube/SonarCloud project key (e.g. `my-org_my-service`). Optional if `sonarqube/project-key` meta annotation is set. |
| `sonarqube_base_url` | `https://sonarcloud.io` | API base URL. Override for self-hosted SonarQube. |
