# Lunar-Lib Growth Roadmap: Next 50 Collectors & Policies

Prioritized plan for expanding lunar-lib with high-mass-appeal, free/OSS-friendly collectors and policies.

**Goal:** Build 50 new items (collectors + policies) that are relevant to the widest possible range of companies, fueling early growth. Prioritize free/open-source tools that don't require paid vendor accounts.

**Audience:** AI agents (Devin, Cursor, etc.) picking up individual items to implement autonomously.

---

## Current Inventory (as of March 2026)

**21 collectors:** ai-use, ast-grep, ci-otel, claude, codecov, codeowners, docker, dr-docs, github, golang, java, jira, k8s, nodejs, python, readme, rust, semgrep, snyk, syft, terraform

**24 policies:** ai-use, codeowners, compliance-docs, container, container-scan, dependencies, feature-flags, golang, iac, iac-scan, java, k8s, linter, nodejs, python, readme, rust, sast, sbom, sca, terraform, testing, ticket, vcs

---

## How to Use This Document

1. **Pick an item** from the prioritized list below.
2. **Read the playbook** at `.ai-implementation/LUNAR-PLUGIN-PLAYBOOK-AI.md` — it covers the full PR lifecycle.
3. **Read the ai-context docs** — especially `collector-reference.md`, `policy-reference.md`, and `strategies.md`.
4. **Follow the spec-first PR flow** — YAML manifest + README first, then implementation after review.
5. **Test thoroughly** using the patterns described in each item's "Testing" section.

---

## Prioritization Criteria

Each item is scored on:

| Criterion | Weight | Meaning |
|-----------|--------|---------|
| **Universality** | High | How many companies need this regardless of stack? |
| **Free/OSS** | High | Can we develop and demo without vendor accounts? |
| **Dev Speed** | Medium | How quickly can an AI agent build and test this? |
| **Policy Value** | High | What guardrails does this enable? |
| **Schema Gap** | Medium | Does this fill a Component JSON category already defined but unpopulated? |

---

## Batch 1: Items 1–12 (Highest Impact, Build First)

### 1. Gitleaks — Secret Scanning

**Type:** Collector + Policy  
**Priority:** 🔴 Critical — fills biggest schema gap  
**Est. Dev Time:** 2–3 days  
**Tool:** [Gitleaks](https://github.com/gitleaks/gitleaks) — 100% free, OSS, 18k+ stars, single Go binary  
**Strategy:** Strategy 5 (Auto-Running Scanners) — code hook  
**Schema Gap:** `.secrets` category is defined in Component JSON but has zero collectors feeding it

**What to build:**

- **Collector (code hook):** Auto-run `gitleaks detect --source . --report-format json` on every commit. Parse JSON output. Write findings to `.secrets`.
- **Policy checks:**
  - `secret-scan-executed` — Assert `.secrets` data exists (scan ran)
  - `no-secrets-in-code` — Assert `.secrets.findings.total == 0`

**Component JSON output:**

```json
{
  "secrets": {
    "source": { "tool": "gitleaks", "version": "8.x" },
    "findings": { "total": 0 },
    "clean": true,
    "issues": []
  }
}
```

**Testing:**

- **Collector tests:**
  - Create a test repo with a known secret (e.g., `AWS_SECRET_ACCESS_KEY=AKIA...` in a file) → verify collector detects it and writes correct JSON
  - Clean repo → verify collector writes `{"secrets": {"clean": true, "findings": {"total": 0}}}`
  - Repo with `.gitleaksignore` → verify allowlisted secrets are excluded
- **Policy tests:**
  - Feed clean component JSON → expect PASS
  - Feed component JSON with findings → expect FAIL with descriptive message
  - Feed component JSON with no `.secrets` key → expect SKIP (no scanner ran)
- **Integration:** Run collector on `pantalasa-cronos/backend`, then feed output to policy. Backend is a clean Go repo so should PASS.

**Docker image note:** Gitleaks is a single static binary. Add it to a custom image based on `earthly/lunar-lib:base-main`, or download in `install.sh`. Prefer adding to image for speed.

---

### 2. Trivy — Container & Filesystem Vulnerability Scanning

**Type:** Collector (multi-sub-collector) + feeds existing policies  
**Priority:** 🔴 Critical — free alternative to Snyk, fills container-scan gap  
**Est. Dev Time:** 3–4 days  
**Tool:** [Trivy](https://github.com/aquasecurity/trivy) — 100% free, OSS, 24k+ stars  
**Strategy:** Strategy 5 (Auto-Running Scanners) — code hook  
**Schema Gap:** `.container_scan` policy exists but no free scanner feeds it data

**What to build:**

- **Sub-collector `filesystem`:** Run `trivy fs --format json .` to scan source code dependencies for known vulns. Write to `.sca` (feeds existing `sca` policy). This gives every Lunar user free SCA without Snyk.
- **Sub-collector `image`:** If Dockerfiles exist, run `trivy image --format json <image>` against built images. Write to `.container_scan` (feeds existing `container-scan` policy).
- **Sub-collector `config`:** Run `trivy config --format json .` to scan IaC misconfigurations. Write to `.iac` scan data (feeds existing `iac-scan` policy).

**Component JSON output (filesystem sub-collector):**

```json
{
  "sca": {
    "source": { "tool": "trivy", "version": "0.x", "integration": "auto" },
    "vulnerabilities": { "critical": 0, "high": 2, "medium": 5, "low": 10, "total": 17 },
    "findings": [
      { "severity": "high", "package": "lodash", "version": "4.17.20", "cve": "CVE-2021-23337", "fix_version": "4.17.21", "fixable": true }
    ],
    "summary": { "has_critical": false, "has_high": true, "all_fixable": true }
  }
}
```

**Testing:**

- **Filesystem sub-collector:** Run on `pantalasa-cronos/frontend` (Node.js) — should detect known npm vulns. Run on `pantalasa-cronos/backend` (Go) — may or may not have vulns; verify JSON shape is correct either way.
- **Config sub-collector:** Run on a repo with Terraform files → verify IaC misconfigs detected. Run on a repo without IaC → verify no data written (don't write empty objects).
- **Policy integration:** Capture Trivy filesystem output → feed to existing `sca` policy → verify pass/fail behavior matches expectations.
- **Edge case:** Repo with no lock files or dependencies → Trivy should find nothing, collector should write nothing.

**Docker image note:** Trivy is ~50MB binary. Must be in a custom Docker image. Consider a shared `earthly/lunar-lib:security-scanners-main` image with Gitleaks + Trivy to amortize image size.

---

### 3. GitHub Actions Security — Workflow File Analysis

**Type:** Collector + Policy  
**Priority:** 🔴 High — supply chain attack vector, every GHA user  
**Est. Dev Time:** 2–3 days  
**Tool:** None required — pure YAML parsing  
**Strategy:** Strategy 8 (File Parsing and Schema Extraction) — code hook

**What to build:**

- **Collector (code hook):** Parse all `.github/workflows/*.yml` files. For each workflow, extract:
  - Actions used and whether they're pinned to SHA vs tag
  - `permissions:` block (present? broad? minimal?)
  - Use of `pull_request_target` (dangerous trigger)
  - Secrets passed via `env:` to third-party actions
- **Policy checks:**
  - `actions-pinned` — All third-party actions pinned to full SHA (not `@v1`)
  - `actions-permissions-set` — `permissions:` block is explicitly set (not relying on defaults)
  - `actions-minimal-permissions` — No `write-all` or overly broad permissions

**Component JSON output:**

```json
{
  "ci": {
    "github_actions": {
      "workflows": [
        {
          "path": ".github/workflows/ci.yml",
          "permissions_set": true,
          "permissions_minimal": true,
          "actions": [
            { "uses": "actions/checkout@v4", "pinned_to_sha": false, "is_official": true },
            { "uses": "docker/build-push-action@abc123def", "pinned_to_sha": true, "is_official": false }
          ],
          "uses_pull_request_target": false
        }
      ],
      "summary": {
        "all_pinned": false,
        "all_permissions_set": true,
        "unpinned_count": 1
      }
    }
  }
}
```

**Testing:**

- **Collector:** Run on `pantalasa-cronos/backend` (has GHA workflows) → verify actions are extracted correctly. Create a test workflow with intentionally unpinned actions and broad permissions → verify detection.
- **Policy:** Feed JSON with all-pinned actions → PASS. Feed JSON with unpinned third-party action → FAIL. Feed JSON with no `.ci.github_actions` → SKIP (not a GHA user).
- **Edge case:** Workflow with `uses: ./local-action` (local actions don't need SHA pinning). Workflow with reusable workflow calls (`uses: org/repo/.github/workflows/x.yml@main`).
- **No external dependencies needed** — this is pure shell + yq/jq parsing. Can test entirely locally.

---

### 4. Dependabot/Renovate — Dependency Update Automation

**Type:** Collector + Policy  
**Priority:** 🟡 High  
**Est. Dev Time:** 1.5–2 days  
**Tool:** None — file existence checks  
**Strategy:** Strategy 8 (File Parsing and Schema Extraction) — code hook

**What to build:**

- **Collector (code hook):** Check for dependency update configuration:
  - `.github/dependabot.yml` → parse ecosystems, update frequency, target branch
  - `renovate.json` / `renovate.json5` / `.renovaterc` / `.renovaterc.json` → parse config
- **Policy checks:**
  - `dependency-updates-configured` — At least one update tool is configured
  - `all-ecosystems-covered` — Every detected package ecosystem (npm, go, pip, docker, github-actions) has a corresponding update config entry

**Component JSON output:**

```json
{
  "repo": {
    "dependency_updates": {
      "configured": true,
      "tool": "dependabot",
      "ecosystems": ["npm", "docker", "github-actions"],
      "update_frequency": "weekly"
    }
  }
}
```

**Testing:**

- **Collector:** Run on `pantalasa-cronos/backend` — check if dependabot.yml or renovate config exists. If not, add one for testing. Run on a repo with both dependabot and renovate → verify correct detection.
- **Policy:** Feed JSON with full ecosystem coverage → PASS. Feed JSON with `npm` project but only `docker` in dependabot config → FAIL (missing ecosystem). Feed JSON with no config → FAIL.
- **Edge case:** Monorepo with multiple directories in dependabot config. Renovate with `extends: ["config:base"]` (presets).

---

### 5. Checkov — IaC Security Scanning

**Type:** Collector  
**Priority:** 🟡 High  
**Est. Dev Time:** 2–3 days  
**Tool:** [Checkov](https://github.com/bridgecrewio/checkov) — free, OSS, 7k+ stars, Python-based  
**Strategy:** Strategy 5 (Auto-Running Scanners) — code hook  
**Feeds:** Existing `iac-scan` policy

**What to build:**

- **Collector (code hook):** Auto-run `checkov -d . --output json --compact` on repos with IaC files (Terraform, CloudFormation, K8s manifests, Dockerfiles). Parse JSON results. Write to `.iac` scan paths that the existing `iac-scan` policy reads.

**Component JSON output:**

```json
{
  "iac": {
    "scan": {
      "source": { "tool": "checkov", "version": "3.x" },
      "findings": {
        "critical": 0, "high": 3, "medium": 8, "low": 2, "total": 13
      },
      "issues": [
        { "severity": "high", "check_id": "CKV_AWS_18", "check_name": "Ensure the S3 bucket has access logging enabled", "file": "main.tf", "resource": "aws_s3_bucket.data" }
      ],
      "summary": { "passed": 45, "failed": 13, "skipped": 2 }
    }
  }
}
```

**Testing:**

- **Collector:** Run on `pantalasa-cronos/backend` or a repo with Terraform files → verify findings are detected. Run on repo with no IaC → verify nothing is written.
- **Policy integration:** Capture Checkov output → feed to existing `iac-scan` policy → verify pass/fail.
- **Docker image note:** Checkov is Python-based (~200MB). Needs its own image or a `security-scanners` image.
- **Important:** Check what the existing `iac-scan` policy expects as input paths. The Checkov collector must write data in the format the existing policy reads.

---

### 6. OpenSSF Scorecard — Supply Chain Security Scoring

**Type:** Collector + Policy  
**Priority:** 🟡 High  
**Est. Dev Time:** 2–3 days  
**Tool:** [OpenSSF Scorecard](https://github.com/ossf/scorecard) — free, backed by Google/OSSF  
**Strategy:** Strategy 5 (Auto-Running Scanners) — code hook or cron  

**What to build:**

- **Collector:** Run `scorecard --repo=<component-url> --format=json`. Parses 18+ checks (branch protection, CI tests, dependency review, fuzzing, signed releases, etc.). Writes aggregate score and per-check results.
- **Policy checks:**
  - `scorecard-minimum-score` — Aggregate score ≥ configurable threshold (default: 5/10)
  - `scorecard-critical-checks` — Specific checks must pass (e.g., `Branch-Protection`, `Token-Permissions`)

**Component JSON output:**

```json
{
  "repo": {
    "scorecard": {
      "source": { "tool": "ossf-scorecard", "version": "5.x" },
      "score": 7.2,
      "checks": [
        { "name": "Branch-Protection", "score": 8, "reason": "branch protection is enabled" },
        { "name": "Token-Permissions", "score": 0, "reason": "non-read permissions detected" }
      ]
    }
  }
}
```

**Testing:**

- **Collector:** Run against a public GitHub repo (e.g., `pantalasa-cronos/backend` if public). Scorecard requires repo to be on a supported platform (GitHub, GitLab) and may need `GITHUB_TOKEN` for rate limits.
- **Policy:** Feed JSON with score 7 (threshold 5) → PASS. Feed JSON with score 3 → FAIL. Feed JSON with missing critical check → FAIL.
- **Note:** Scorecard CLI needs network access to query GitHub API. This means it works as a `cron` collector or `code` collector with network. Test with `--local` flag where possible for offline testing.
- **Note:** Lunar already provides some of these checks natively (branch protection via `github` collector + `vcs` policy). The value of Scorecard is the industry-standard score that procurement teams ask for, plus checks we don't cover yet (signed releases, fuzzing, SAST).

---

### 7. GitHub Actions Security Policy (ci-security)

**Type:** Policy only (uses data from item #3 collector)  
**Priority:** 🟡 High  
**Est. Dev Time:** 1 day (if collector from item #3 exists)  
**Strategy:** Policy on collected data

**Note:** This is the policy side of item #3. Listed separately because the collector and policy can be separate PRs. The collector (#3) writes data; this policy reads it. Can be built by a different agent in parallel once the Component JSON schema from #3 is agreed upon in spec review.

---

### 8. .NET/C# Language Support

**Type:** Collector + Policy  
**Priority:** 🟡 High — C# is #5 most popular language  
**Est. Dev Time:** 3–4 days  
**Tool:** None (file parsing) + `dotnet` CLI for CI detection  
**Strategy:** Strategy 8 (File Parsing) + Strategy 1 (CI Detection)

**What to build:**

- **Collector (code hook):** Parse `.csproj`, `.sln`, `Directory.Build.props`. Extract: target framework, NuGet dependencies, package versions.
- **Collector (CI hook):** Detect `dotnet test`, `dotnet build` execution. Capture test results and coverage from Coverlet.
- **Policy checks:** `dotnet-version-minimum`, `dotnet-tests-exist`, `dotnet-coverage-threshold`, `dotnet-lock-file-exists`

**Component JSON paths:** `.lang.dotnet.*` (following the existing `.lang.<language>` convention)

**Testing:**

- Create a minimal .NET project in `pantalasa-cronos` (or fork an existing open-source .NET repo).
- **Collector:** Run on .NET project → verify .csproj parsing, dependency extraction.
- **Policy:** Feed JSON with .NET 8 (minimum 6) → PASS. Feed JSON with .NET 5 (EOL) → FAIL.
- **CI hook:** Set up a GHA workflow with `dotnet test` on the test repo, push to cronos, verify CI collector captures test results.

---

### 9. API Documentation (OpenAPI/Swagger)

**Type:** Collector + Policy  
**Priority:** 🟡 High — fills `.api` schema gap  
**Est. Dev Time:** 2 days  
**Tool:** None (YAML/JSON file detection and parsing)  
**Strategy:** Strategy 8 (File Parsing) — code hook

**What to build:**

- **Collector (code hook):** Find OpenAPI/Swagger spec files (`openapi.yaml`, `openapi.json`, `swagger.yaml`, `swagger.json`, `api-spec.*`). Validate syntax (valid YAML/JSON, has `openapi` or `swagger` key). Extract version, endpoint count, info metadata.
- **Policy checks:**
  - `api-spec-exists` — At least one API spec file found
  - `api-spec-valid` — All found specs parse without errors
  - `api-documented` — Spec has description, contact, and minimum endpoint count

**Component JSON output:**

```json
{
  "api": {
    "specs": [
      { "path": "api/openapi.yaml", "type": "openapi", "version": "3.1.0", "valid": true, "endpoint_count": 15 }
    ],
    "summary": { "spec_exists": true, "all_valid": true, "total_endpoints": 15 }
  }
}
```

**Testing:**

- **Collector:** Add an OpenAPI spec to `pantalasa-cronos/backend` → verify detection and parsing. Run on repo with no API spec → verify nothing written. Add an invalid YAML file named `openapi.yaml` → verify `valid: false`.
- **Policy:** Feed JSON with valid spec → PASS. Feed JSON with no specs → FAIL. Feed JSON with invalid spec → FAIL.
- **No external dependencies** — pure shell + yq. Fast to develop.

---

### 10. Helm Chart Support

**Type:** Collector + Policy  
**Priority:** 🟡 Medium-High  
**Est. Dev Time:** 2–3 days  
**Tool:** `helm` CLI for template rendering/linting  
**Strategy:** Strategy 8 (File Parsing) — code hook

**What to build:**

- **Collector (code hook):** Find `Chart.yaml` files. Parse chart metadata (name, version, appVersion, dependencies). Optionally run `helm lint` and `helm template` for validation. Detect deprecated K8s APIs in rendered templates.
- **Policy checks:**
  - `helm-chart-valid` — Chart passes `helm lint`
  - `helm-no-deprecated-apis` — No deprecated K8s APIs in templates
  - `helm-values-documented` — `values.yaml` has comments or a `values.schema.json` exists

**Component JSON paths:** `.k8s.helm.*` (extends existing `.k8s` category)

**Testing:**

- Add a Helm chart to a `pantalasa-cronos` component, or fork an open-source Helm chart repo.
- **Collector:** Run on chart → verify metadata extracted. Run `helm lint` → verify warnings captured.
- **Policy:** Feed JSON with clean chart → PASS. Feed JSON with deprecated API → FAIL.
- **Docker image:** `helm` binary needs to be in the image. Small binary, easy to add.

---

### 11. SonarQube/SonarCloud Integration

**Type:** Collector  
**Priority:** 🟡 Medium-High  
**Est. Dev Time:** 2–3 days  
**Tool:** SonarCloud free tier (for testing) or status check detection  
**Strategy:** Strategy 2 (GitHub App Status Check) + Strategy 1 (CI Detection)

**What to build:**

- **Sub-collector `github-app`:** Detect SonarCloud GitHub App status checks on PRs (like semgrep/snyk pattern). Extract quality gate status.
- **Sub-collector `cicd`:** Detect `sonar-scanner` or `sonarqube` CLI execution in CI. Extract analysis results.
- **Feeds:** Existing `sast` policy (code quality findings) and `testing` policy (coverage metrics from SonarQube)

**Component JSON output:**

```json
{
  "sast": {
    "source": { "tool": "sonarqube", "integration": "github_app" },
    "native": {
      "sonarqube": {
        "quality_gate": "OK",
        "bugs": 0,
        "vulnerabilities": 2,
        "code_smells": 15,
        "coverage": 82.5
      }
    }
  }
}
```

**Testing:**

- **GitHub App sub-collector:** Install SonarCloud free tier on a `pantalasa-cronos` public repo. Open a PR → verify status check is detected and parsed.
- **CI sub-collector:** Add a SonarScanner step to a GHA workflow → verify CI detection.
- **Note:** SonarCloud is free for open-source repos. For testing, fork a public repo to `pantalasa-cronos` and connect SonarCloud to it.
- **Follows the exact same pattern as `semgrep` and `snyk` collectors** — use those as templates.

---

### 12. PHP Language Support

**Type:** Collector + Policy  
**Priority:** 🟡 Medium  
**Est. Dev Time:** 2–3 days  
**Tool:** None (file parsing) + PHPUnit for CI detection  
**Strategy:** Strategy 8 (File Parsing) + Strategy 1 (CI Detection)

**What to build:**

- **Collector (code hook):** Parse `composer.json` / `composer.lock`. Extract: PHP version requirement, dependencies (require/require-dev), scripts.
- **Collector (CI hook):** Detect `phpunit`, `composer test`, `php artisan test` execution. Capture test results and coverage.
- **Policy checks:** `php-version-minimum`, `php-tests-exist`, `php-lock-file-exists`, `php-coverage-threshold`

**Component JSON paths:** `.lang.php.*` (following `.lang.<language>` convention)

**Testing:**

- Fork a minimal Laravel or Symfony project to `pantalasa-cronos`, or create a simple `composer.json` project.
- **Collector:** Run on PHP project → verify composer.json parsing, dependency extraction.
- **Policy:** Feed JSON with PHP 8.2 (min 8.0) → PASS. Feed JSON with PHP 7.4 (EOL) → FAIL.
- **CI hook:** Add PHPUnit CI workflow, push to cronos, verify test results captured.

---

## Batch 2: Items 13–25 (High Impact)

| # | Item | Type | Tool/Strategy | Est. Days | Mass Appeal | Notes |
|---|------|------|---------------|-----------|-------------|-------|
| 13 | **GitLab CI security** | Collector + Policy | File parsing `.gitlab-ci.yml` | 2–3 | 8/10 | Same concept as #3 but for GitLab. Parse for image pinning, secret exposure. Test by creating a GitLab project. |
| 14 | **Backstage catalog-info.yaml** | Collector + Policy | File parsing `catalog-info.yaml` | 2 | 8/10 | Service catalog standard. Check entity fields, annotations, dependencies. Test with sample catalog files. |
| 15 | **PagerDuty on-call** | Collector + Policy | PagerDuty API (free tier available) | 3 | 7/10 | Verify on-call schedules, min participants, escalation. Needs `PAGERDUTY_API_KEY` secret. Test with PagerDuty free account. |
| 16 | **Datadog/Grafana dashboards** | Collector + Policy | Vendor API | 3 | 7/10 | Verify monitoring dashboards exist per service. Needs API keys. Test with Grafana (free/OSS). |
| 17 | **OWASP ZAP** | Collector | ZAP CLI (free, OSS) | 3 | 7/10 | Dynamic security scanning for web apps. Auto-run against URLs. Test against a sample app. |
| 18 | **Gradle** (enhance Java) | Collector | File parsing `build.gradle` | 2 | 7/10 | Gradle-specific build parsing. Test with `pantalasa-cronos/spring-petclinic` or similar. |
| 19 | **Code complexity** | Collector + Policy | radon (Python), gocyclo (Go) | 2 | 7/10 | McCabe/cognitive complexity. Auto-run scanners. Test on existing pantalasa repos. |
| 20 | **Makefile/build-script** | Collector + Policy | File parsing | 1.5 | 7/10 | Check for `make build/test/lint` targets. Pure file parsing. Easy to test. |
| 21 | **Pre-commit hooks** | Collector + Policy | File parsing | 1.5 | 6/10 | Detect `.pre-commit-config.yaml`, husky, lefthook. Pure file parsing. |
| 22 | **EditorConfig + formatter** | Collector + Policy | File parsing | 1 | 6/10 | `.editorconfig`, prettier, black config exists. Trivial to build. |
| 23 | **Docker Compose** | Collector + Policy | File parsing | 1.5 | 6/10 | `docker-compose.yml` for local dev. Parse services, check for dev compose file. |
| 24 | **GitHub repo settings expansion** | Collector | GitHub API | 2 | 7/10 | Topics, visibility, description, vulnerability alerts enabled. Expands existing `github` collector. |
| 25 | **endoflife.date EOL checking** | Collector + Policy | endoflife.date API (free) | 2–3 | 8/10 | Cross-reference runtime/framework versions against endoflife.date. Needs network (cron or code hook). |

**Testing notes for Batch 2:**
- Items 13, 14, 20–23 are pure file parsing — testable entirely locally with `lunar collector dev`.
- Items 15–16 need vendor API access — create free-tier accounts for testing, or mock API responses for unit tests.
- Item 25 needs network to call endoflife.date API — test as cron collector.

---

## Batch 3: Items 26–38 (Broader Platform Coverage)

| # | Item | Type | Tool/Strategy | Est. Days | Notes |
|---|------|------|---------------|-----------|-------|
| 26 | **OpsGenie on-call** | Collector + Policy | OpsGenie API | 3 | Alternative to PagerDuty. Same policy shape. |
| 27 | **Ruby language support** | Collector + Policy | File parsing + CI detection | 3 | Parse Gemfile, detect RSpec/Minitest. Fork a Rails app to cronos. |
| 28 | **Swift/Kotlin mobile** | Collector | File parsing | 3 | Parse Package.swift, build.gradle.kts. Niche but growing. |
| 29 | **CloudFormation** | Collector | File parsing | 2 | AWS-native IaC. Parse YAML/JSON templates. |
| 30 | **Pulumi** | Collector | File parsing | 2 | Modern IaC. Parse Pulumi.yaml, detect language. |
| 31 | **ArgoCD/Flux GitOps** | Collector + Policy | File parsing | 2 | GitOps deployment detection. Parse Application CRDs. |
| 32 | **Cosign image signing** | Collector + Policy | cosign CLI (free) | 2 | Container image signing verification. |
| 33 | **Renovate detailed** | Collector | File parsing | 2 | Deep Renovate config analysis beyond "exists". |
| 34 | **BitBucket support** | Collector | BitBucket API | 3 | Third major git platform. Branch protection, PR settings. |
| 35 | **Jenkins pipeline** | Collector | File parsing `Jenkinsfile` | 2 | Still very common in enterprise. |
| 36 | **CircleCI** | Collector | File parsing `.circleci/config.yml` | 2 | Popular hosted CI. |
| 37 | **Azure DevOps** | Collector | File parsing `azure-pipelines.yml` + API | 3 | Major enterprise CI/CD. |
| 38 | **Buildkite** | Collector | File parsing `.buildkite/pipeline.yml` | 2 | Modern CI, popular with scale-ups. |

**Testing notes for Batch 3:**
- CI platform items (35–38) are file parsing of pipeline configs — testable locally.
- VCS platform items (34) need API access — use BitBucket Cloud free tier.
- GitOps items (31) can be tested with sample CRDs in cronos repos.

---

## Batch 4: Items 39–50 (Specialized but Valuable)

| # | Item | Type | Tool/Strategy | Est. Days | Notes |
|---|------|------|---------------|-----------|-------|
| 39 | **Terraform Cloud/Spacelift** | Collector | Vendor API | 3 | IaC platform-level data. |
| 40 | **AWS CDK** | Collector | File parsing | 2 | Programmatic IaC. Parse `cdk.json`, detect constructs. |
| 41 | **SLSA provenance** | Policy | Uses existing data | 1.5 | Supply chain attestation verification. |
| 42 | **OpenAPI linting (Spectral)** | Collector + Policy | Spectral CLI (free) | 2 | API quality beyond "spec exists". Auto-run Spectral. |
| 43 | **Database migration tracking** | Collector + Policy | File parsing | 2 | Flyway, Alembic, Liquibase, golang-migrate detection. |
| 44 | **Changelog** | Collector + Policy | File parsing | 1 | CHANGELOG.md / keep-a-changelog standards. |
| 45 | **SECURITY.md** | Collector + Policy | File parsing | 1 | Security vulnerability reporting process. |
| 46 | **CONTRIBUTING.md** | Collector + Policy | File parsing | 1 | Contribution guidelines presence. |
| 47 | **Dev container** | Collector + Policy | File parsing | 1 | `.devcontainer/devcontainer.json` configuration. |
| 48 | **Grafana alerting rules** | Collector | Grafana API | 2 | Alert rule verification for SRE teams. |
| 49 | **Linear/GitHub Issues** | Collector | API | 2 | Expand ticket tracking beyond Jira. |
| 50 | **Runtime EOL via endoflife.date** | Collector | endoflife.date API | 2 | Language runtime EOL checking. |

---

## General Testing Guidance for AI Agents

### Local Testing (Fast Iteration)

```bash
# 1. Test collector output
cd /home/brandon/code/earthly/pantalasa-cronos/lunar
lunar collector dev <plugin>.<sub-collector> \
  --component github.com/pantalasa-cronos/backend \
  --verbose

# 2. Capture collector output for policy testing
lunar collector dev <plugin>.<sub> \
  --component github.com/pantalasa-cronos/backend 2>&1 | \
  grep '^{' | jq -s 'reduce .[] as $item ({}; . * $item)' > /tmp/collected.json

# 3. Test policy against collected data
lunar policy dev <plugin>.<check> --component-json /tmp/collected.json

# 4. Test policy against live hub data
lunar component get-json github.com/pantalasa-cronos/backend > /tmp/component.json
lunar policy dev <plugin>.<check> --component-json /tmp/component.json
```

### Test Matrix (Every Plugin Must Cover)

| Scenario | Collector Expected | Policy Expected |
|----------|--------------------|-----------------|
| **Data present** | Writes correct JSON | PASS |
| **No data** (e.g., Go policy on Python repo) | Writes nothing | SKIP |
| **Partial data** (some fields missing) | Writes what exists | Graceful (PASS/FAIL, not ERROR) |
| **Tool not installed** | Exit 0, stderr message | N/A |
| **Missing secrets** | Exit 0, stderr message | N/A |

### Docker Container Testing

Many auto-run scanners need binaries in the container. Always test inside the Docker container:

```bash
# Build image
earthly +image

# Test script inside container
docker run --rm -v /path/to/test/repo:/workspace \
  -w /workspace \
  earthly/lunar-lib:<image-name> \
  bash -c "source /path/to/script.sh"
```

### Alpine/BusyBox Gotchas

The base image uses Alpine. Common failures:
- `grep -P` doesn't work → use `sed -n 's/pattern/\1/p'`
- `grep --include` doesn't work → use `find -name '*.ext' -exec grep ...`
- `awk` capture groups don't work → use `sed` or `substr(s, RSTART, RLENGTH)`

### Pantalasa-Cronos Test Components

| Component | Language | Good For Testing |
|-----------|----------|------------------|
| `github.com/pantalasa-cronos/backend` | Go | Go collector, Docker, GHA, branch protection |
| `github.com/pantalasa-cronos/frontend` | Node.js | Node collector, npm vulns, ESLint |
| `github.com/pantalasa-cronos/auth` | Python | Python collector, pip deps |
| `github.com/pantalasa-cronos/spring-petclinic` | Java | Java/Maven/Gradle, JaCoCo |

You can add files (Helm charts, OpenAPI specs, .NET projects, etc.) to these repos freely for testing. Cronos is a sandbox.
