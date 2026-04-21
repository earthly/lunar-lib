# SonarQube Collector

Detect SonarQube/SonarCloud across four integration points — Web API,
in-repo config, CI scanner runs, and the GitHub App PR check.

## Overview

Four sub-collectors give a complete picture of SonarQube usage for a
component: `api` (daily cron, Web API snapshot), `config` (detects in-repo
SonarQube configuration), `cicd` (captures `sonar-scanner` runs), and
`github-app` (reads SonarCloud's GitHub App PR check). Results land in the
tool-agnostic `.code_quality` category, with SonarQube-specific structure
stashed under `.code_quality.native.sonarqube`. Works against both SonarQube
self-hosted and SonarCloud — only `sonarqube_base_url` differs.

## Collected Data

This collector writes to the following Component JSON paths. The top-level
`.code_quality.*` fields are **tool-agnostic** and intended for a generic
code-quality policy. SonarQube-specific structure (the rating split, quality
gate detail, SQALE debt, native metric names, config/CI/GitHub-App payloads)
lives under `.code_quality.native.sonarqube` for SonarQube-aware policies.

| Path | Type | Written by | Description |
|------|------|-----------|-------------|
| `.code_quality.source` | object | `api` | Tool, integration, project key, and API URL |
| `.code_quality.passing` | bool | `api` | Overall pass/fail signal — derived from SonarQube's quality gate status |
| `.code_quality.coverage_percentage` | number | `api` | Line coverage percentage (0–100), if measured |
| `.code_quality.duplication_percentage` | number | `api` | Duplicated lines percentage (0–100), if measured |
| `.code_quality.issue_counts` | object | `api` | Severity buckets: `total`, `critical`, `high`, `medium`, `low` (same shape as `.sca` / `.sast`) |
| `.code_quality.native.sonarqube.quality_gate` | object | `api` | Quality gate status (`OK`/`WARN`/`ERROR`) and failed condition count |
| `.code_quality.native.sonarqube.ratings` | object | `api` | SonarQube letter ratings (A–E) per dimension: reliability, security, maintainability, security review |
| `.code_quality.native.sonarqube.metrics` | object | `api` | SonarQube-native metric names: bugs, vulnerabilities, code smells, lines of code |
| `.code_quality.native.sonarqube.config` | object | `config` | Paths to SonarQube config files discovered in the repo |
| `.code_quality.native.sonarqube.cicd` | object | `cicd` | `sonar-scanner` invocations captured in CI: command, version, exit code |
| `.code_quality.native.sonarqube.github_app` | object | `github-app` | SonarCloud GitHub App PR check: state, context, target URL |

## Collectors

This integration provides the following sub-collectors. Use `include` in
`lunar-config.yml` to select a subset.

| Collector | Hook | Description |
|-----------|------|-------------|
| `api` | cron (daily) | Queries the SonarQube/SonarCloud Web API for quality gate status, ratings, and metrics |
| `config` | code | Detects `sonar-project.properties`, `sonar-maven-plugin`, `org.sonarqube` Gradle plugin, or `<SonarQubeEnabled>` in `.csproj` |
| `cicd` | `ci-after-command` on `sonar-scanner` | Captures `sonar-scanner` invocations in CI (mirrors `snyk/cli`). Maven and Gradle launchers are follow-ups. |
| `github-app` | code (PRs only) | Reads the SonarCloud GitHub App's check run on each PR (mirrors `snyk/github-app`) |

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
- `SONARQUBE_TOKEN` — SonarQube/SonarCloud user token with `Browse` permission on the target project (used by the `api` sub-collector). Sent as the HTTP Basic username with an empty password, per the SonarQube Web API convention.
- `GH_TOKEN` — GitHub token with read access to PR check runs (used by the `github-app` sub-collector).

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
