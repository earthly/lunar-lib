# SonarQube Collector

Detect SonarQube/SonarCloud across five integration points — default-branch
Web API, PR Web API, in-repo config, CI scanner runs, and the GitHub App PR
check.

## Overview

Five sub-collectors give a complete picture of SonarQube usage for a
component: `branch` (per-commit Web API on the default branch), `pr` (per-PR
Web API, scoped with `pullRequest=`), `config` (detects in-repo SonarQube
configuration), `cicd` (captures `sonar-scanner` runs), and `github-app`
(reads SonarCloud's GitHub App PR check). Users who don't gate PRs with
SonarQube can simply exclude the `pr` (and `github-app`) sub-collectors from
`lunar-config.yml`. Results land in the tool-agnostic `.code_quality`
category, with SonarQube-specific structure stashed under
`.code_quality.native.sonarqube`. Works against both SonarQube self-hosted
and SonarCloud — only `sonarqube_base_url` differs.

## Collected Data

This collector writes to the following Component JSON paths. The top-level
`.code_quality.*` fields are **tool-agnostic** and intended for a generic
code-quality policy. SonarQube-specific structure (the rating split, quality
gate detail, SQALE debt, native metric names, config/CI/GitHub-App payloads)
lives under `.code_quality.native.sonarqube` for SonarQube-aware policies.

| Path | Type | Written by | Description |
|------|------|-----------|-------------|
| `.code_quality.source` | object | `branch` / `pr` | Tool, integration (`branch` or `pr`), project key, API URL, and `analysis_status` (`complete` or `pending`) |
| `.code_quality.passing` | bool | `branch` / `pr` | Overall pass/fail signal — derived from SonarQube's quality gate status |
| `.code_quality.coverage_percentage` | number | `branch` / `pr` | Line coverage percentage (0–100), if measured |
| `.code_quality.duplication_percentage` | number | `branch` / `pr` | Duplicated lines percentage (0–100), if measured |
| `.code_quality.issue_counts` | object | `branch` / `pr` | Severity buckets: `total`, `critical`, `high`, `medium`, `low` (same shape as `.sca` / `.sast`) |
| `.code_quality.native.sonarqube.quality_gate` | object | `branch` / `pr` | Quality gate status (`OK`/`WARN`/`ERROR`) and failed condition count |
| `.code_quality.native.sonarqube.ratings` | object | `branch` / `pr` | SonarQube letter ratings (A–E) per dimension: reliability, security, maintainability, security review |
| `.code_quality.native.sonarqube.metrics` | object | `branch` / `pr` | SonarQube-native metric names: bugs, vulnerabilities, code smells, lines of code |
| `.code_quality.native.sonarqube.config` | object | `config` | Paths to SonarQube config files discovered in the repo |
| `.code_quality.native.sonarqube.cicd` | object | `cicd` | `sonar-scanner` invocations captured in CI: command, version, exit code |
| `.code_quality.native.sonarqube.github_app` | object | `github-app` | SonarCloud GitHub App PR check: state, context, target URL, and `status` (`complete` or `pending`) |

## Collectors

This integration provides the following sub-collectors. Use `include` in
`lunar-config.yml` to select a subset.

| Collector | Hook | Description |
|-----------|------|-------------|
| `branch` | code (default branch only) | Queries the SonarQube/SonarCloud Web API with `branch=<default-branch>` per-commit. Polls for analysis completion before returning metrics (see [Analysis completion & polling](#analysis-completion--polling)). |
| `pr` | code (PRs only) | Queries the Web API with `pullRequest=<PR number>` per-commit. Same polling behaviour as `branch`. Exclude this sub-collector if you don't want SonarQube data on PRs. |
| `config` | code | Detects `sonar-project.properties`, `sonar-maven-plugin`, `org.sonarqube` Gradle plugin, or `<SonarQubeEnabled>` in `.csproj` |
| `cicd` | `ci-after-command` on `sonar-scanner` | Captures `sonar-scanner` invocations in CI (mirrors `snyk/cli`). Maven and Gradle launchers are follow-ups. |
| `github-app` | code (PRs only) | Reads the SonarCloud GitHub App's check run on each PR (mirrors `snyk/github-app`). Polls for the check run to appear. |

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
- `SONARQUBE_TOKEN` — SonarQube/SonarCloud user token with `Browse` permission on the target project (used by the `branch` and `pr` sub-collectors). Sent as the HTTP Basic username with an empty password, per the SonarQube Web API convention.
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

### Analysis completion & polling

SonarQube's Compute Engine queues analyses asynchronously — when CI finishes
uploading a scan via `sonar-scanner`, the results aren't immediately visible
on the Web API. Typical latency is 10–60 seconds; large projects can take
several minutes. The `branch` and `pr` sub-collectors handle this race by
polling `api/project_analyses/search` until the most recent analysis's
`revision` matches the current `head_sha`, or until
`api_poll_timeout_seconds` elapses. If the timeout hits, they write
`.code_quality.source.analysis_status = "pending"` with no metrics — policies
that care about "is SonarQube wired up at all?" can still read the `config`
sub-collector's output, and policies that want to gate on fresh results can
treat `analysis_status == "pending"` as a skip rather than a fail.

The same principle applies to `github-app`: the SonarCloud check run on a PR
appears only after analysis completes, so the sub-collector polls the GitHub
Checks API up to `github_app_poll_timeout_seconds` and writes
`.code_quality.native.sonarqube.github_app.status = "pending"` on timeout.

If your CI already waits for SonarQube analysis to complete before invoking
`lunar` (e.g. using `sonar-scanner`'s `-Dsonar.qualitygate.wait=true`), set
the relevant `*_poll_timeout_seconds` input to `0` for a single-shot query.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `project_key` | *(empty — falls back to catalog meta)* | SonarQube/SonarCloud project key (e.g. `my-org_my-service`). Optional if `sonarqube/project-key` meta annotation is set. |
| `sonarqube_base_url` | `https://sonarcloud.io` | API base URL. Override for self-hosted SonarQube. |
| `api_poll_timeout_seconds` | `180` | Total seconds `branch`/`pr` wait for a SonarQube analysis matching `head_sha`. `0` disables polling. |
| `api_poll_interval_seconds` | `10` | Seconds between polls while waiting for SonarQube analysis. |
| `github_app_poll_timeout_seconds` | `180` | Total seconds `github-app` waits for the SonarCloud GitHub check run on the PR head SHA. `0` disables polling. |
| `github_app_poll_interval_seconds` | `10` | Seconds between polls while waiting for the SonarCloud check run. |
