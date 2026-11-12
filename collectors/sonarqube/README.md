# SonarQube Collector

Detect SonarQube/SonarCloud via read-only Web API queries, optional
auto-run of `sonar-scanner`, in-repo config, CI scanner runs, and
SonarQube's pull request check on GitHub.

## Overview

Five sub-collectors cover SonarQube: `api` reads an existing analysis via
the Web API, `auto` runs `sonar-scanner` itself and then reads the result
back, `config` flags in-repo configuration, `cicd` captures CI scanner
runs, and `github-app` reads the check SonarQube posts on each pull request. `api`
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
| `.code_quality.source` | object | `api` / `auto` / `github-app` | Tool, integration (`api`, `auto` or `github_app`), project key, API URL, and (`api` / `auto`) `analysis_status` (`complete` or `pending`) |
| `.code_quality.passing` | bool | `api` / `auto` / `github-app` | Overall pass/fail signal — derived from SonarQube's quality gate status |
| `.code_quality.pr` | object | `github-app` | The pull request's new-code numbers from SonarQube's check: `new_issues`, `fixed_issues`, `accepted_issues`, `security_hotspots`, `coverage_percentage`, `duplication_percentage`. Only the numbers the check prints, so a missing key means no data, not 0 |
| `.code_quality.coverage_percentage` | number | `api` / `auto` | Line coverage percentage (0–100), if measured |
| `.code_quality.duplication_percentage` | number | `api` / `auto` | Duplicated lines percentage (0–100), if measured |
| `.code_quality.issues` | object | `api` / `auto` | Severity buckets: `total`, `critical`, `high`, `medium`, `low` (same shape as `.sca.vulnerabilities` / `.sast.findings`) |
| `.code_quality.native.sonarqube.quality_gate` | object | `api` / `auto` / `github-app` | Quality gate status (`OK`/`WARN`/`ERROR`) and failed condition count; from `github-app`, also `failed_conditions[]` as SonarQube lists them (`text`, plus `metric`, `value` and `required` when it gives them) |
| `.code_quality.native.sonarqube.ratings` | object | `api` / `auto` | SonarQube letter ratings (A–E) per dimension: reliability, security, maintainability, security review |
| `.code_quality.native.sonarqube.metrics` | object | `api` / `auto` | SonarQube-native metric names: bugs, vulnerabilities, code smells, lines of code |
| `.code_quality.native.sonarqube.auto` | object | `auto` | Scanner run metadata: `version`, `exit_code`, `duration_seconds`, and `status` (`complete` or `scanner-failed`) |
| `.code_quality.native.sonarqube.config` | object | `config` | Paths to SonarQube config files discovered in the repo |
| `.code_quality.native.sonarqube.cicd` | object | `cicd` | `sonar-scanner` invocations captured in CI: command, version, exit code |
| `.code_quality.native.sonarqube.github_app` | object | `github-app` | `status` (`complete`, or `pending` on timeout) and the SonarQube `check_runs[]` read: `name`, `project_key`, `conclusion`, `title`, `url`, `completed_at`, and `quality_gate` (`passed`/`failed`, absent when the check reports no gate, such as a failed analysis) |

## Collectors

This integration provides the following sub-collectors. Use `include` in
`lunar-config.yml` to select a subset.

| Collector | Hook | Description |
|-----------|------|-------------|
| `api` | code | Queries the SonarQube/SonarCloud Web API per-commit. On default-branch commits the query is scoped with `branch=<default>`; on PR commits with `pullRequest=<PR number>`. Polls for analysis completion before returning metrics (see [Analysis completion & polling](#analysis-completion--polling)). Narrow `runs_on` on the import to only run on default-branch or only on PRs. |
| `auto` | code | Downloads/invokes `sonar-scanner` on the checked-out source — with `-Dsonar.branch.name=<default>` on default-branch commits, or `-Dsonar.pullrequest.*` on PR commits — then polls the Web API and writes the same fields as `api` with `"integration": "auto"`. Requires `SONARQUBE_TOKEN` with `Execute Analysis`. Exclude when users run `sonar-scanner` themselves (see [Auto-run vs API-read](#auto-run-vs-api-read)). |
| `config` | code | Detects `sonar-project.properties`, `sonar-maven-plugin`, `org.sonarqube` Gradle plugin, or `<SonarQubeEnabled>` in `.csproj` |
| `cicd` | `ci-after-command` on `sonar-scanner` | Captures `sonar-scanner` invocations in CI (mirrors `snyk/cli`). Maven and Gradle launchers are follow-ups. |
| `github-app` | code (PRs only) | Reads SonarQube's check run on each PR, on github.com or GitHub Enterprise Server: the quality gate, its failed conditions and the new-code numbers. Needs no project key or SonarQube token. Polls for the check run to complete. |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/sonarqube@v1.0.0
    on: ["domain:your-domain"]
    include:
      - api         # Analysis results from the Web API
      - config      # Sonar config in the repo
      - cicd        # sonar-scanner runs in CI
      - github-app  # SonarQube's check run on PRs
    # with:
    #   project_key: "my-org_my-service"        # Optional — falls back to catalog meta annotation
    #   sonarqube_base_url: "https://sonarcloud.io"  # Or your self-hosted SonarQube URL
```

Required secrets:
- `SONARQUBE_TOKEN` — SonarQube/SonarCloud user token. For read-only `api` use, `Browse` permission on the target project is sufficient. For `auto`, which runs `sonar-scanner` itself, the token also needs `Execute Analysis` permission. Sent as the HTTP Basic username with an empty password, per the SonarQube Web API convention.
- `GH_TOKEN` — GitHub token that can read the repository's check runs (Checks read on a fine-grained token, `repo` on a classic one), used by `github-app`. For components on GitHub Enterprise Server, set `GH_ENTERPRISE_TOKEN`; without it, `GH_TOKEN` is used there too. Or use a [GitHub App](#github-app).

### Project key discovery

The collector resolves the SonarQube project key in this order:

1. **Catalog meta annotation** — reads `sonarqube/project-key` from the component's lunar catalog meta. Set via `lunar catalog component --meta sonarqube/project-key <key>`, typically invoked by a company-specific cataloger that knows which components map to which SonarQube projects. This is the recommended approach for orgs where each component has its own project.
2. **Explicit `project_key` input** — set in `lunar-config.yml` for static cases, or when importing the collector multiple times with different `on:` scopes (e.g. one import per domain, each with its own project).
3. **Neither found** — the collector exits cleanly with no data written.

### Auto-run vs API-read

Three triggers produce the same `.code_quality.*` data — pick the one that
matches how SonarQube is wired up for your component:

| Trigger | Sub-collectors to include |
|---------|---------------------------|
| User runs `sonar-scanner` in CI | `api`, `cicd`, `github-app` |
| Collector auto-runs the scan | `auto`, `github-app` |
| Read-only (scan happens elsewhere, not in this CI) | `api` |
| PR quality gate only, with no project key or SonarQube token | `github-app` |

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
mechanisms (plugin-level `runs_on` on a vendored copy, or leaving the
sub-collector out of `include` for a domain that only exercises one side).

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
Both `api` and `auto` handle this race by polling until the analysis of the
current `head_sha` is published, or until `api_poll_timeout_seconds`
elapses:

- On default-branch commits, until the newest analysis in
  `api/project_analyses/search` has that `revision`.
- On PR commits, until the PR's entry in `api/project_pull_requests/list`
  is for that commit. SonarCloud reports the analyzed commit there.
  SonarQube Server doesn't, so there the PR's latest analysis must be no
  older than the commit; a scan of the previous push that started after
  this commit was made still counts.

If the timeout hits, they write
`.code_quality.source.analysis_status = "pending"` with no metrics —
policies that care about "is SonarQube wired up at all?" can still read
the `config` sub-collector's output, and policies that want to gate on
fresh results can treat `analysis_status == "pending"` as a skip rather
than a fail.

The same applies to `github-app`: SonarQube posts its check on a PR only
after analyzing the commit, so the sub-collector polls the commit's check
runs up to `github_app_poll_timeout_seconds` and writes
`.code_quality.native.sonarqube.github_app.status = "pending"` if the check
hasn't completed by then. When your scanner runs late in CI, raise the
timeout to cover it.

### SonarQube's pull request check

`github-app` reads the check SonarQube Server and SonarQube Cloud post on a
pull request's head commit: "SonarQube Code Analysis" or "SonarCloud Code
Analysis", prefixed with the project name in a monorepo. It works on
github.com and GitHub Enterprise Server alike, needs no project key, and
never calls SonarQube, so it needs no SonarQube token and no route from Lunar
to your SonarQube.

- **Which check.** Only a check that links to that pull request's SonarQube
  analysis (`pullRequest=<n>`) counts. Branch analyses of the same commit,
  other pull requests, and CI jobs or code-scanning checks with "Sonar" in
  their name are left out. When SonarQube analyzes the commit again, the
  newest check wins.
- **Several projects.** With the `sonarqube/project-key` meta or the
  `project_key` input set, it reads only that project's check and waits for
  it. Without one, it reads every project that reported, and the gate
  passes only if all of them pass.
- **What it records.** The gate (`.code_quality.passing` and
  `quality_gate`) with the failed conditions, and the new-code numbers in
  `.code_quality.pr`. These are the pull request's numbers, not the
  project's overall coverage or issue counts, which only `api` reads.
  SonarQube prints only the failed conditions on a failed gate, and says
  "No data about Coverage" when there's nothing to measure; a number it
  doesn't print is left out rather than written as 0. A failed analysis is
  recorded without a gate.
- **Errors.** Rate limits and 5xx responses are retried until the timeout.
  Any other GitHub error, such as a token that can't see the repository,
  fails the run instead of writing `pending`.

The `code-quality` policy's `executed` and `passing` checks, and the
`sonarqube` policy's `quality-gate-passing` check, work from `github-app`
alone. The coverage, duplication, issue and rating thresholds need `api` or
`auto`.

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `project_key` | *(empty — falls back to catalog meta)* | SonarQube/SonarCloud project key (e.g. `my-org_my-service`). Optional if `sonarqube/project-key` meta annotation is set. |
| `sonarqube_base_url` | `https://sonarcloud.io` | API base URL. Override for self-hosted SonarQube. |
| `api_poll_timeout_seconds` | `180` | Total seconds `api`/`auto` wait for a SonarQube analysis matching `head_sha`. |
| `api_poll_interval_seconds` | `10` | Seconds between polls while waiting for SonarQube analysis. |
| `auto_scanner_version` | `7.0.0.4796` | Pinned version of `sonar-scanner` used by `auto`. Ignored if the collector image already ships with `sonar-scanner` on PATH. |
| `auto_sources` | `.` | Value passed to `-Dsonar.sources=` by `auto`. Override for monorepos. |
| `auto_extra_args` | *(empty)* | Extra command-line args appended to every `auto` `sonar-scanner` invocation (e.g. `-Dsonar.exclusions=**/*.min.js`). |
| `github_app_poll_timeout_seconds` | `180` | Total seconds `github-app` waits for SonarQube's check run on the PR head commit. A waiting run holds one of the Hub's collection workers. |
| `github_app_poll_interval_seconds` | `10` | Seconds between polls while waiting for SonarQube's check run. |

### GitHub App

To use a token from a GitHub App instead of `GH_TOKEN`, add the App with `lunar github-app add` and set `github_app` to its name. The token is minted for each component's own host and owner, so one name can hold an App on github.com and another on GitHub Enterprise Server. Grant it read access to Checks (used by `github-app`); a token request for a permission the App lacks fails, and the collector falls back to the secret. It must be installed on every repository this collector runs on, since a repository outside the installation answers 404 like one that doesn't exist.
