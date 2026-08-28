# CodeQL Collector

Detects GitHub CodeQL security scans and collects scan metadata from GitHub Code Scanning or CLI integrations.

## Overview

This collector detects CodeQL static analysis via GitHub's Code Scanning integration or CLI usage in CI pipelines. CodeQL is GitHub's semantic code analysis engine — unlike pattern-matching tools, it compiles source code into a relational database and queries it for vulnerabilities using inter-procedural data flow analysis.

All data is written to the `.sast` category, enabling tool-agnostic SAST policies that work across CodeQL, Semgrep, Snyk Code, and other SAST tools.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.sast.source` | object | Source metadata (`tool`, `integration`, optional `version`) |
| `.sast.findings` | object | Severity counts: `critical`, `high`, `medium`, `low`, `total` |
| `.sast.issues[]` | array | Individual findings with `severity`, `rule`, `file`, `line`, `message` |
| `.sast.summary` | object | `has_critical`, `has_high` booleans |
| `.sast.native.codeql.github_app` | object | Raw GitHub Code Scanning check-run data |
| `.sast.native.codeql.cicd` | object | CodeQL CLI invocations detected in CI |
| `.sast.native.codeql.sarif` | object | Raw SARIF output from CodeQL analysis (when available) |
| `.sast.running_in_prs` | boolean | Compliance proof that PRs are being scanned |
| `.sast.source.fanout` | object | *(monorepo-fanout, on each subcomponent)* Provenance — root component, root SHA, path patterns used, matched count, fingerprint |
| `.sast.native.monorepo_fanout` | object | *(monorepo-fanout, on the ROOT only)* Per-target written/skipped breadcrumb |

## Collectors

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `github-app` | code (PRs only) | Detects CodeQL via GitHub Code Scanning check-runs |
| `running-in-prs` | code (default branch) | Proves CodeQL is running on PRs (compliance proof for default branch) |
| `cicd` | ci-after-command | Detects `codeql` and legacy `codeql-runner` executions in CI, collects SARIF |
| `monorepo-fanout` | after-json (`.sast.issues`) | Redistributes a monorepo's repo-wide findings to its subdirectory components by file path. Enable on the repository ROOT alongside `cicd`. Writes each subcomponent's severity counts (`.sast.findings`/`.sast.summary`) plus provenance; `.sast.native` stays on the root. Subcomponents are discovered with a prefix-scoped SQL query, and a finding reaches a subcomponent when its file matches that component's `paths:` plus the implicit `<subdir>/*`. A subcomponent with zero matches is still written with `total: 0`, which turns its SAST policy from "no data" into a pass; one that already has its own SAST scan is never overwritten. Requires Hub v3.3.0+, and the root needs at least one policy or the after-json wave is never dispatched |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/codeql@main
    on: ["domain:your-domain"]
    secrets:
      GH_TOKEN: ${GH_TOKEN}
```

The `github-app` collector requires a `GH_TOKEN` secret for GitHub API access. CodeQL posts check-runs via the `github-advanced-security` app. The collector queries the check-runs API, filters by this app slug, and waits for completion.

The `cicd` collector matches both `codeql` and `codeql-runner` (legacy) binary executions in CI. When the traced command is `codeql database analyze` or `codeql database interpret-results` with a `--output=` flag, the collector reads the SARIF file from disk and collects it as raw data plus normalized findings counts and issues.

The `running-in-prs` collector queries the Lunar Hub database to verify PR scanning. It uses `lunar sql connection-string` to obtain database credentials. If unavailable, the collector skips silently.

### Monorepos

CodeQL analyses a whole repository, and the traced scan resolves to the
repository — so in a monorepo the findings land on the repo-root component while
the real components are the subdirectories, which all read as "No SAST scanning
data found" despite having been scanned. `monorepo-fanout` closes that gap.
Three things have to be true:

1. the monorepo's **root** needs a component of its own — it is where the
   repo-wide scan lands and where the fan-out runs;
2. `cicd` has to be enabled on that root, since it is what writes the
   `.sast.issues` the fan-out reads;
3. **at least one policy must also evaluate the root.** An `after-json`
   collector is dispatched by the Hub's doneness gate, and that gate is only
   consulted while bundling a component's policies — so a component that no
   policy evaluates never fires its after-json collectors at all. Watch the
   interaction with domains: a policy declared with no `on:` resolves to
   `domain:other`, so putting the root in a dedicated domain (sensible on its
   own terms) can silently take it out of every fleet policy's scope.

```yaml
components:
  # The repository root. A scan carrier, not a deployable service — its own
  # domain keeps your service guardrails off it.
  github.com/acme/repo:
    owner: platform@acme.com
    domain: engineering.monorepo-roots
    branch: "main"

  # Subcomponents are unchanged.
  github.com/acme/repo/services/api:
    domain: engineering.services
    paths: ["services/api/*"]

collectors:
  - uses: github://earthly/lunar-lib/collectors/codeql@main
    on: ["component:github.com/acme/repo"]
    include: [cicd, monorepo-fanout]
    secrets:
      GH_TOKEN: ${GH_TOKEN}
    # with:
    #   # Off by default: no SAST policy reads .sast.issues, so the per-finding
    #   # array is not shipped to every subcomponent unless you want the detail
    #   # visible per service.
    #   include_issues: "false"
    #   # Raise on a Hub that materializes slowly (a repo_sync backlog starves
    #   # the mat drain, and a SHA-pinned read waits on it).
    #   read_retry_seconds: "300"

policies:
  # Point 3 above — without a policy on the root, the fan-out never dispatches.
  - uses: github://earthly/lunar-lib/policies/sast@main
    on: ["component:github.com/acme/repo"]
    include: [executed]
```

Because the wave is fire-once per `(component, sha, pr)`, re-testing a change
needs a fresh commit — re-running CI on the same commit will not re-fire it.
