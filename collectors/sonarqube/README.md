# SonarQube Collector

Detect SonarQube/SonarCloud via read-only Web API queries, optional
auto-run of `sonar-scanner`, in-repo config, CI scanner runs, and the
GitHub App PR check.

## Overview

Five sub-collectors cover SonarQube: `api` reads an existing analysis via
the Web API, `auto` runs `sonar-scanner` itself and then reads the result
back, `config` flags in-repo configuration, `cicd` captures CI scanner
runs, and `github-app` reads the SonarCloud GitHub App PR check. `api`
and `auto` are alternate paths to the same `.code_quality.*` data — pick
one per context (see [Auto-run vs API-read](#auto-run-vs-api-read)). Both
run on default-branch and PR commits by default, branching internally on
`LUNAR_COMPONENT_PR` — narrow `runs_on` on the import to restrict scope.
Tool-agnostic fields land at `.code_quality.*`; SonarQube-specific
structure lives under `.code_quality.native.sonarqube`. Both self-hosted
SonarQube and SonarCloud are supported via `sonarqube_base_url`.

## Collected Data

This collector writes to the following Component JSON paths. The top-level
`.code_quality.*` fields are **tool-agnostic** and intended for a generic
code-quality policy. SonarQube-specific structure (the rating split, quality
gate detail, SQALE debt, native metric names, config/CI/GitHub-App payloads)
lives under `.code_quality.native.sonarqube` for SonarQube-aware policies.

| Path | Type | Written by | Description |
|------|------|-----------|-------------|
| `.code_quality.source` | object | `api` / `auto` | Tool, integration (`api` or `auto`), project key, API URL, and `analysis_status` (`complete` or `pending`) |
| `.code_quality.passing` | bool | `api` / `auto` | Overall pass/fail signal — derived from SonarQube's quality gate status |
| `.code_quality.coverage_percentage` | number | `api` / `auto` | Line coverage percentage (0–100), if measured |
| `.code_quality.duplication_percentage` | number | `api` / `auto` | Duplicated lines percentage (0–100), if measured |
| `.code_quality.issue_counts` | object | `api` / `auto` | Severity buckets: `total`, `critical`, `high`, `medium`, `low` (same shape as `.sca` / `.sast`) |
| `.code_quality.native.sonarqube.quality_gate` | object | `api` / `auto` | Quality gate status (`OK`/`WARN`/`ERROR`) and failed condition count |
| `.code_quality.native.sonarqube.ratings` | object | `api` / `auto` | SonarQube letter ratings (A–E) per dimension: reliability, security, maintainability, security review |
| `.code_quality.native.sonarqube.metrics` | object | `api` / `auto` | SonarQube-native metric names: bugs, vulnerabilities, code smells, lines of code |
| `.code_quality.native.sonarqube.auto` | object | `auto` | Scanner run metadata: `version`, `exit_code`, `duration_seconds`, and `status` (`complete` or `scanner-failed`) |
| `.code_quality.native.sonarqube.config` | object | `config` | Paths to SonarQube config files discovered in the repo |
| `.code_quality.native.sonarqube.cicd` | object | `cicd` | `sonar-scanner` invocations captured in CI: command, version, exit code |
| `.code_quality.native.sonarqube.github_app` | object | `github-app` | SonarCloud GitHub App PR check: state, context, target URL, and `status` (`complete` or `pending`) |

## Collectors

This integration provides the following sub-collectors. Use `include` in
`lunar-config.yml` to select a subset.

| Collector | Hook | Description |
|-----------|------|-------------|
| `api` | code | Queries the SonarQube/SonarCloud Web API per-commit. On default-branch commits the query is scoped with `branch=<default>`; on PR commits with `pullRequest=<PR number>`. Polls for analysis completion before returning metrics (see [Analysis completion & polling](#analysis-completion--polling)). Narrow `runs_on` on the import to only run on default-branch or only on PRs. |
| `auto` | code | Downloads/invokes `sonar-scanner` on the checked-out source — with `-Dsonar.branch.name=<default>` on default-branch commits, or `-Dsonar.pullrequest.*` on PR commits — then polls the Web API and writes the same fields as `api` with `"integration": "auto"`. Requires `SONARQUBE_TOKEN` with `Execute Analysis`. Exclude when users run `sonar-scanner` themselves (see [Auto-run vs API-read](#auto-run-vs-api-read)). |
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
- `SONARQUBE_TOKEN` — SonarQube/SonarCloud user token. For read-only `api` use, `Browse` permission on the target project is sufficient. For `auto`, which runs `sonar-scanner` itself, the token also needs `Execute Analysis` permission. Sent as the HTTP Basic username with an empty password, per the SonarQube Web API convention.
- `GH_TOKEN` — GitHub token with read access to PR check runs (used by the `github-app` sub-collector).

### Project key discovery

The collector resolves the SonarQube project key in this order:

1. **Catalog meta annotation** — reads `sonarqube/project-key` from the component's lunar catalog meta. Set via `lunar catalog component --meta sonarqube/project-key <key>`, typically invoked by a company-specific cataloger that knows which components map to which SonarQube projects. This is the recommended approach for orgs where each component has its own project.
2. **Explicit `project_key` input** — set in `lunar-config.yml` for static cases, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own project).
3. **Neither found** — the collector exits cleanly with no data written.

### Auto-run vs API-read

Three triggers produce the same `.code_quality.*` data — pick the one that
matches how SonarQube is wired up for your component:

| Trigger | Sub-collectors to include | Sub-collectors to exclude |
|---------|---------------------------|---------------------------|
| User runs `sonar-scanner` in CI | `api`, `cicd`, `github-app` | `auto` |
| Collector auto-runs the scan | `auto`, `github-app` | `api`, `cicd` |
| Read-only (scan happens elsewhere, not in this CI) | `api` | `auto`, `cicd` |

The `config` sub-collector is orthogonal — it flags whether SonarQube is
wired up at all — and is safe to include in every configuration.

Including both `api` and `auto` for the same context runs the scanner once
and then reads the API twice (wasteful but not harmful); including `auto`
alongside a user-run `sonar-scanner` in CI double-scans the project, which
is more expensive and may hit rate limits on the SonarQube server. A
future collector-dependency feature will let `auto` fire conditionally —
only when the `cicd` sub-collector didn't capture a scan for the current
`head_sha`.

Each of `api` and `auto` runs on both default-branch and PR commits by
default. Scope narrowing is per sub-collector via the usual platform
mechanisms (plugin-level `runs_on` on a vendored copy, or excluding the
sub-collector entirely with `exclude:` when scoping by domain that only
exercises one side).

### SonarQube vs SonarCloud

Both SonarQube (self-hosted) and SonarCloud expose the same Web API. Select
the instance by overriding `sonarqube_base_url`:

| Instance | `sonarqube_base_url` |
|----------|----------------------|
| SonarCloud (default) | `https://sonarcloud.io` |
| SonarQube self-hosted | e.g. `https://sonar.example.com` |

Tokens are created the same way on both — in the user profile under **Security → Generate Tokens**.

### Analysis completion & polling

SonarQube's Compute Engine queues analyses asynchronously — when a scan
finishes uploading (via user-run `sonar-scanner` or our own `auto`
invocation), the results aren't immediately visible on the Web API.
Typical latency is 10–60 seconds; large projects can take several minutes.
Both `api` and `auto` handle this race by polling
`api/project_analyses/search` until the most recent analysis's `revision`
matches the current `head_sha`, or until `api_poll_timeout_seconds`
elapses. If the timeout hits, they write
`.code_quality.source.analysis_status = "pending"` with no metrics —
policies that care about "is SonarQube wired up at all?" can still read
the `config` sub-collector's output, and policies that want to gate on
fresh results can treat `analysis_status == "pending"` as a skip rather
than a fail.

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
| `api_poll_timeout_seconds` | `180` | Total seconds `api`/`auto` wait for a SonarQube analysis matching `head_sha`. `0` disables polling. |
| `api_poll_interval_seconds` | `10` | Seconds between polls while waiting for SonarQube analysis. |
| `auto_scanner_version` | `7.0.0.4796` | Pinned version of `sonar-scanner` used by `auto`. Ignored if the collector image already ships with `sonar-scanner` on PATH. |
| `auto_sources` | `.` | Value passed to `-Dsonar.sources=` by `auto`. Override for monorepos. |
| `auto_extra_args` | *(empty)* | Extra command-line args appended to every `auto` `sonar-scanner` invocation (e.g. `-Dsonar.exclusions=**/*.min.js`). |
| `github_app_poll_timeout_seconds` | `180` | Total seconds `github-app` waits for the SonarCloud GitHub check run on the PR head SHA. `0` disables polling. |
| `github_app_poll_interval_seconds` | `10` | Seconds between polls while waiting for the SonarCloud check run. |
