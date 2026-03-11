# Lunar-Lib Growth Roadmap: Collectors & Policies

Prioritized plan for expanding lunar-lib with high-mass-appeal, free/OSS-friendly collectors and policies.

**Goal:** Build a library large enough that any new customer can select ~50 collectors and policies from it and get meaningful results immediately. All policies should be imported at `score` level initially; customers can promote to `report-pr` or `block-pr` later.

**Audience:** AI agents (Devin, Cursor, etc.) picking up individual items to implement autonomously.

---

## Tiers

### 🟢 Starter — Zero Config, Zero Secrets

Import and it works. No configuration, no secrets, no vendor accounts. Collectors skip gracefully when a technology isn't present, policies skip when underlying data is absent. Every customer gets these on day one. Items can be removed if not wanted, but they're designed to "just work" out of the box.

### 🟡 Starter+ — Light Configuration or Secrets

Easy to set up but requires a secret (API key, token) or a URL to connect to an external service. Examples: Snyk (needs `SNYK_TOKEN`), Jira (needs `JIRA_URL` + `JIRA_TOKEN`). Can't import blindly on day one — needs a quick setup step.

### 🔵 Advanced — Specific Use Cases or Significant Configuration

For specific use cases or requires meaningful configuration to be useful. Examples: ast-grep (needs custom rule definitions), ci-otel (needs OpenTelemetry endpoint), OWASP ZAP (needs target URLs).

---

## Current Inventory (as of March 2026)

**21 collectors:** ai-use, ast-grep, ci-otel, claude, codecov, codeowners, docker, dr-docs, github, golang, java, jira, k8s, nodejs, python, readme, rust, semgrep, snyk, syft, terraform

**24 policies:** ai-use, codeowners, compliance-docs, container, container-scan, dependencies, feature-flags, golang, iac, iac-scan, java, k8s, linter, nodejs, python, readme, rust, sast, sbom, sca, terraform, testing, ticket, vcs

---

## 🟢 Starter

### Collectors

| # | Plugin | Category | Notes |
|---|--------|----------|-------|
| 1 | `readme` | Repo health | Every repo |
| 2 | `codeowners` | Ownership | Every repo |
| 3 | `github` | VCS settings | Branch protection, repo settings |
| 4 | `docker` | Containers | Skips if no Dockerfiles. 🆕 Add `hadolint` sub-collector for auto-run Dockerfile linting. |
| 5 | `k8s` | Infrastructure | Skips if no K8s manifests |
| 6 | `terraform` | Infrastructure | Skips if no `.tf` files |
| 7 | `syft` | SBOM | Auto-generates SBOM for any repo |
| 8 | `semgrep` | SAST | Detects Semgrep usage, skips if absent |
| 9 | `golang` | Language | Skips if not Go |
| 10 | `java` | Language | Skips if not Java |
| 11 | `nodejs` | Language | Skips if not Node |
| 12 | `python` | Language | Skips if not Python |
| 13 | `rust` | Language | Skips if not Rust |
| 14 | 🆕 `php` | Language | Skips if not PHP |
| 15 | 🆕 `dotnet` | Language | Skips if not .NET |
| 16 | 🆕 `ruby` | Language | Skips if not Ruby. Parse Gemfile, detect Bundler. |
| 17 | 🆕 `cpp` | Language | Skips if no C/C++ files. Detect CMakeLists.txt, Makefile, `.c`/`.cpp`/`.h`. |
| 18 | 🆕 `shell` | Language + linting | Skips if no `.sh` files. Auto-runs ShellCheck for linting. |
| 19 | 🆕 `web` | Language | Skips if no `.html`/`.css` files. Basic frontend detection. |
| 20 | 🆕 `gitleaks` | Secret scanning | Auto-runs on every repo. Zero config. |
| 21 | 🆕 `trivy` | SCA + container | Auto-runs free vuln scanning. Zero config. |
| 22 | 🆕 `checkov` | IaC scanning | Auto-runs on repos with IaC/Dockerfiles. Zero config. Feeds `iac-scan` policy. |
| 23 | 🆕 `actionlint` | GHA linting | Auto-lints GitHub Actions workflow files for syntax errors, type mismatches, deprecated features. Different from `gha-security` (which checks permissions/pinning). |
| 25 | 🆕 `gha-security` | CI security | Parses GHA workflows for pinned actions, permissions, `pull_request_target` misuse. Skips if no `.github/workflows/`. |
| 26 | 🆕 `api-docs` | API specs | Detects OpenAPI/Swagger specs, skips if none |
| 27 | 🆕 `repo-hygiene` | Repo health | Scans for standard files (.gitignore, LICENSE, CI config, .dockerignore, SECURITY.md, CONTRIBUTING.md, .editorconfig) |

### Policies

| # | Plugin | Checks | Notes |
|---|--------|--------|-------|
| 28 | 🆕 `repo-hygiene` | `readme-exists`, `readme-min-length`, `codeowners-exists`, `codeowners-valid`, `codeowners-catchall`, `gitignore-exists`, `license-exists`, `ci-config-exists`, `dockerignore-exists`, `security-md-exists`, `contributing-md-exists`, `editorconfig-exists` | Consolidates `readme` + `codeowners` + new standard file checks |
| 29 | `vcs` | Branch protection, approvals, no force push | You should have branch protection |
| 30 | `container` | Dockerfile best practices | Skips if no Dockerfiles |
| 31 | `container-scan` | No critical image vulns | Skips if no scan data |
| 32 | `k8s` | Resource limits, probes, PDBs | Skips if no K8s manifests |
| 33 | `terraform` | Provider pinning, state backend | Skips if no `.tf` files |
| 34 | `iac` | General IaC standards | Skips if no IaC data |
| 35 | `iac-scan` | No critical IaC misconfigs | Skips if no scan data |
| 36 | `sbom` | SBOM exists, license compliance | Skips if no SBOM data |
| 37 | `sast` | SAST scan executed | Skips if no SAST data |
| 38 | `sca` | No critical vulns | Skips if no SCA data |
| 39 | `dependencies` | Lock files, versions | Skips per language |
| 40 | `linter` | Lint configured | Skips if not detected |
| 41 | `testing` | `executed`, `passing` only | Skips if no `.lang.*`; coverage checks are Starter+ |
| 42 | `golang` | Go-specific checks | Skips if not Go |
| 43 | `java` | Java-specific checks | Skips if not Java |
| 44 | `nodejs` | Node-specific checks | Skips if not Node |
| 45 | `python` | Python-specific checks | Skips if not Python |
| 46 | `rust` | Rust-specific checks | Skips if not Rust |
| 47 | 🆕 `php` | PHP-specific checks | Skips if not PHP |
| 48 | 🆕 `dotnet` | .NET-specific checks | Skips if not .NET |
| 49 | 🆕 `ruby` | Ruby-specific checks | Skips if not Ruby |
| 50 | 🆕 `secrets` | No secrets in code | On Gitleaks data; skips if no scan data |
| 51 | 🆕 `ci-security` | Pinned actions, minimal permissions | Skips if no GHA workflows |
| 52 | 🆕 `api-docs` | OpenAPI/Swagger spec exists, valid | Skips if no API spec detected |

### Planned change: `repo-hygiene` consolidation

The `repo-hygiene` plugin is a new collector + policy pair that consolidates the existing `readme` and `codeowners` policies and adds standard file checks:

**Collector** scans for standard files and writes presence data. **Policy** folds existing `readme` + `codeowners` policy checks and adds:

- `gitignore-exists` — `.gitignore` file present
- `license-exists` — `LICENSE` or `LICENSE.md` present
- `ci-config-exists` — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`, or `buildkite/` detected
- `dockerignore-exists` — `.dockerignore` present when Dockerfiles exist (conditional)
- `security-md-exists` — `SECURITY.md` present
- `contributing-md-exists` — `CONTRIBUTING.md` present
- `editorconfig-exists` — `.editorconfig` present

The existing `readme` and `codeowners` collector plugins remain separate (they collect different data). Only the policies merge into `repo-hygiene`.

---

## 🟡 Starter+

Requires light configuration (a secret, a URL, or a toggle). Easy to set up but not zero-config.

**Vendor integrations:**

| # | Item | Type | Config Needed |
|---|------|------|---------------|
| S1 | `jira` collector + `ticket` policy | Both | `JIRA_URL`, `JIRA_TOKEN` |
| S2 | 🆕 `linear` collector + `ticket` policy | Both | `LINEAR_API_KEY` |
| S3 | `snyk` collector | Collector | `SNYK_TOKEN` |
| S3 | `codecov` collector | Collector | `CODECOV_TOKEN` (or auto-detects via GHA) |
| S4 | 🆕 `sonarqube` collector | Collector | SonarCloud GitHub App or `SONAR_TOKEN` |
| S5 | 🆕 `pagerduty` collector + `oncall` policy | Both | `PAGERDUTY_API_KEY` |
| S6 | 🆕 `opsgenie` collector + `oncall` policy | Both | `OPSGENIE_API_KEY` |
| S7 | 🆕 `backstage` collector + `catalog` policy | Both | `catalog-info.yaml` path convention |
| S9 | 🆕 `datadog` collector + `observability` policy | Both | `DATADOG_API_KEY` |
| S10 | 🆕 `grafana` collector + `observability` policy | Both | `GRAFANA_URL`, `GRAFANA_API_KEY` |

**Infrastructure (needs tool in image or config):**

| # | Item | Type | Config Needed |
|---|------|------|---------------|
| S11 | 🆕 `helm` collector + policy | Both | `helm` binary in image |
| S12 | 🆕 `dependabot` collector + `renovate` collector + `dep-automation` policy | Both | Separate collectors for each tool, shared policy. Aspirational — fails if no dep update tool configured. |
| S13 | 🆕 `endoflife` collector + policy | Both | Needs network for endoflife.date API |

**Testing & quality:**

| # | Item | Type | Config Needed |
|---|------|------|---------------|
| S14 | `testing` policy (coverage checks) | Policy | Threshold config (`min_coverage`) |
| S15 | `compliance-docs` + `dr-docs` | Both | File path conventions |
| S16 | `feature-flags` policy | Policy | Flag library patterns |

---

## 🔵 Advanced

Requires significant configuration, custom rules, or is for very specific use cases.

| # | Item | Type | Why Advanced |
|---|------|------|-------------|
| A1 | `ast-grep` collector | Collector | Needs custom YAML rule definitions to be useful |
| A2 | `ci-otel` collector | Collector | Needs OpenTelemetry endpoint configuration |
| A3 | `claude` collector | Collector | Needs `ANTHROPIC_API_KEY` + custom prompts |
| A4 | `ai-use` collector + policy | Both | AI governance — organizational policy decision |
| A5 | 🆕 `openssf` collector + policy | Both | Needs network, niche compliance use case |
| A6 | 🆕 `owasp-zap` collector | Collector | Needs target URLs, web app specific |
| A7 | 🆕 `cosign` collector + `signing` policy | Both | Needs signing keys, supply chain specific |
| A8 | 🆕 `code-complexity` collector + policy | Both | Needs threshold tuning per codebase |
| A9 | 🆕 `argocd-flux` collector + `gitops` policy | Both | GitOps-specific deployment pattern |
| A10 | 🆕 `cloudformation` collector | Collector | AWS-specific IaC |
| A11 | 🆕 `pulumi` collector | Collector | Pulumi-specific IaC |
| A12 | 🆕 `pre-commit` collector + policy | Both | Pre-commit hook specific |
| A13 | 🆕 `docker-compose` collector + policy | Both | Local dev specific |

**CI platforms:**

| # | Item | Type | Why Advanced |
|---|------|------|-------------|
| A14 | 🆕 `jenkins` collector | Collector | Jenkins-specific pipeline parsing |
| A15 | 🆕 `circleci` collector | Collector | CircleCI-specific config parsing |
| A16 | 🆕 `azure-devops` collector | Collector | Azure DevOps-specific |
| A17 | 🆕 `buildkite` collector | Collector | Buildkite-specific |

---

## Example 50-Packs by Company Type

### Pack A: Regulated Enterprise (Fintech / Healthcare / Gov)

**Profile:** 500+ engineers. Java/.NET/Go. K8s + Terraform + Helm. Snyk + SonarQube. Jira. PagerDuty. SOC2/PCI/HIPAA.

| Source | Items | Count |
|--------|-------|-------|
| 🟢 Starter | All ~52 | 52 |
| 🟡 `jira` collector + `ticket` policy | Ticket traceability | +2 |
| 🟡 `snyk` collector | Enterprise SCA | +1 |
| 🟡 `sonarqube` collector | Code quality gate | +1 |
| 🟡 `testing` (coverage checks) | Coverage enforcement | +1 |
| 🟡 `compliance-docs` + `dr-docs` | DR plan compliance | +2 |
| 🟡 `helm` collector + policy | Helm chart validation | +2 |
| 🟡 `pagerduty` + `oncall` policy | On-call verification | +2 |
| 🟡 `dependabot` + `renovate` + `dep-automation` | Dep update tracking | +3 |
| 🔵 `cosign` + `signing` policy | Image signing | +2 |
| **Total** | | **~67** |

**What the CISO gets:** Secret scanning (Gitleaks), vulnerability scanning (Snyk + Trivy), SBOM + license compliance, IaC security (Checkov), Dockerfile linting (hadolint), branch protection, ticket traceability, DR docs, on-call verification, image signing, ShellCheck on deploy scripts.

---

### Pack B: AI-Native Startup

**Profile:** 30–80 engineers. Python-heavy + TypeScript/Go. Docker but no K8s. GHA. Linear. Fast-moving, AI-heavy.

| Source | Items | Count |
|--------|-------|-------|
| 🟢 Starter | All ~52 | 52 |
| 🟡 `linear` collector + `ticket` policy | Linear ticket refs | +2 |
| 🟡 `dependabot` + `renovate` + `dep-automation` | Dep update tracking | +3 |
| 🔵 `ai-use` collector + policy | AI governance | +2 |
| 🔵 `code-complexity` | Complexity limits | +2 |
| **Total** | | **~60** |

**What the CTO gets:** Starter alone covers secret scanning, free SCA, SAST, Dockerfile linting, ShellCheck, API docs, language checks for Python/Node/Go, testing enforcement. Linear integration adds ticket traceability. AI governance tracks coding assistant usage.

---

### Pack C: E-Commerce SaaS

**Profile:** 150–300 engineers. Node.js + PHP (legacy) + Python. Docker + K8s. Terraform. GHA. Jira. Datadog.

| Source | Items | Count |
|--------|-------|-------|
| 🟢 Starter | All ~52 | 52 |
| 🟡 `jira` collector + `ticket` policy | Ticket references | +2 |
| 🟡 `snyk` collector | Paid SCA | +1 |
| 🟡 `testing` (coverage checks) | Coverage enforcement | +1 |
| 🟡 `helm` collector + policy | Helm charts | +2 |
| 🟡 `dependabot` + `renovate` + `dep-automation` | Dep updates | +3 |
| 🟡 `endoflife` | Runtime EOL (PHP 7!) | +2 |
| 🟡 `datadog` + `observability` | Dashboard verification | +2 |
| 🟡 `feature-flags` policy | Flag hygiene | +1 |
| **Total** | | **~65** |

**What the VP Eng gets:** Full polyglot coverage (Node + PHP + Python + Go + Ruby all in Starter), K8s + Terraform safety nets, Dockerfile + shell script linting, Jira traceability, coverage enforcement. The endoflife checker catches neglected legacy PHP services.

---

### Pack D: Platform / Infrastructure Company

**Profile:** 80–200 engineers. Go + Rust primary. Heavy Docker, K8s, Terraform, Helm. GHA or Buildkite. Open-source projects.

| Source | Items | Count |
|--------|-------|-------|
| 🟢 Starter | All ~52 | 52 |
| 🟡 `compliance-docs` + `dr-docs` | Ops maturity | +2 |
| 🟡 `helm` collector + policy | Helm validation | +2 |
| 🟡 `dependabot` + `renovate` + `dep-automation` | Dep updates | +3 |
| 🟡 `feature-flags` policy | Flag lifecycle | +1 |
| 🔵 `cosign` + `signing` policy | Image signing | +2 |
| 🔵 `pre-commit` | Pre-commit hooks | +2 |
| 🔵 `buildkite` collector | Buildkite CI | +1 |
| **Total** | | **~64** |

**What the Head of Platform gets:** Deep infrastructure coverage (K8s + Terraform + Checkov + Helm), Go/Rust language checks, Dockerfile linting (hadolint), shell script linting (ShellCheck), image signing verification, operational readiness docs.

---

## Implementation Priorities (Build Order)

**Phase 1: Complete the Starter tier** (zero-config items for universal baseline)

| Priority | Item | Why | Est. Days |
|----------|------|-----|-----------|
| P1 | **Gitleaks collector + secrets policy** | Fills biggest schema gap, every repo benefits | 2–3 |
| P2 | **Trivy collector** (filesystem + config) | Free SCA + container scan for everyone | 3–4 |
| P3 | **repo-hygiene collector + policy** | Consolidates readme + codeowners + new file checks | 2–3 |
| P4 | **GHA security collector + ci-security policy** | Supply chain security, ~65% of market | 2–3 |
| P5 | **hadolint sub-collector** (add to existing `docker` plugin) | Auto-run Dockerfile linting as new sub-collector | 1–2 |
| P6 | **ShellCheck / shell collector** | Auto-run shell script linting + bash language detection | 2 |
| P7 | **Checkov collector** | Auto-run IaC scanning, feeds existing `iac-scan` policy | 2–3 |
| P8 | **actionlint collector** | Auto-run GHA workflow linting (catches bugs, not just security) | 1–2 |
| P9 | **PHP collector + policy** | Language detection, skip-safe | 2–3 |
| P10 | **.NET/C# collector + policy** | Language detection, skip-safe | 3–4 |
| P11 | **Ruby collector + policy** | Language detection, skip-safe | 2–3 |
| P12 | **C/C++ collector** | Language detection, skip-safe. Optional cppcheck integration. | 2 |
| P13 | **Web (HTML/CSS) collector** | Basic frontend detection, skip-safe | 1 |
| P14 | **API docs collector + policy** | Swagger/OpenAPI detection, skip-safe | 2 |

**Phase 2: Starter+ items** (most common vendor integrations)

| Priority | Item | Est. Days |
|----------|------|-----------|
| P15 | **Helm collector + policy** | 2–3 |
| P16 | **`dependabot` collector + `renovate` collector + `dep-automation` policy** | 2–3 |
| P17 | **SonarQube collector** | 2–3 |
| P18 | **PagerDuty collector + oncall policy** | 3 |
| P19 | **Linear collector + ticket policy** | 2 |
| P20 | **endoflife.date collector + policy** | 2–3 |
| P21 | **Backstage collector + catalog policy** | 2 |
| P22 | **Datadog collector + observability policy** | 3 |
| P23 | **Grafana collector + observability policy** | 3 |
| P24 | **OpsGenie collector + oncall policy** | 3 |

**Phase 3: Advanced items and remaining batch**

Prioritized by customer demand. See Advanced tier and remaining items below.

---

## Remaining Items (Phase 3+)

| # | Item | Type | Tool/Strategy | Est. Days | Notes |
|---|------|------|---------------|-----------|-------|
| 1 | **OpenSSF Scorecard** | Collector + Policy | scorecard CLI | 2–3 | Niche compliance use case |
| 2 | **Datadog/Grafana dashboards** | Collector + Policy | Vendor API | 3 | Dashboard existence verification |
| 3 | **OWASP ZAP** | Collector | ZAP CLI (free) | 3 | Dynamic security scanning |
| 4 | **Gradle** (enhance Java) | Collector | File parsing | 2 | Gradle-specific parsing |
| 5 | **Code complexity** | Collector + Policy | radon, gocyclo | 2 | McCabe/cognitive complexity |
| 6 | **Makefile/build-script** | Collector + Policy | File parsing | 1.5 | Standard build targets |
| 7 | **Pre-commit hooks** | Collector + Policy | File parsing | 1.5 | .pre-commit-config.yaml, husky |
| 8 | **EditorConfig + formatter** | Collector + Policy | File parsing | 1 | .editorconfig, prettier |
| 9 | **Docker Compose** | Collector + Policy | File parsing | 1.5 | docker-compose.yml |
| 10 | **GitHub repo settings expansion** | Collector | GitHub API | 2 | Topics, visibility, alerts |
| 11 | **endoflife.date EOL** | Collector + Policy | API | 2–3 | Runtime EOL checking |
| 12 | **Cosign image signing** | Collector + Policy | cosign CLI | 2 | Image signing verification |
| 13 | **ArgoCD/Flux GitOps** | Collector + Policy | File parsing | 2 | GitOps deployment detection |
| 14 | **CloudFormation** | Collector | File parsing | 2 | AWS IaC |
| 15 | **Pulumi** | Collector | File parsing | 2 | Modern IaC |
| 16 | **Jenkins** | Collector | File parsing | 2 | Jenkinsfile parsing |
| 17 | **CircleCI** | Collector | File parsing | 2 | .circleci/config.yml |
| 18 | **Azure DevOps** | Collector | File parsing | 3 | azure-pipelines.yml |
| 19 | **Buildkite** | Collector | File parsing | 2 | .buildkite/pipeline.yml |
| 20 | **Swift/Kotlin mobile** | Collector | File parsing | 3 | Mobile app support |
| 21 | **Terraform Cloud/Spacelift** | Collector | Vendor API | 3 | IaC platform data |
| 22 | **AWS CDK** | Collector | File parsing | 2 | Programmatic IaC |
| 23 | **SLSA provenance** | Policy | Existing data | 1.5 | Supply chain attestation |
| 24 | **OpenAPI linting (Spectral)** | Collector + Policy | Spectral CLI | 2 | API quality |
| 25 | **Database migration tracking** | Collector + Policy | File parsing | 2 | Flyway, Alembic, Liquibase |
| 26 | **Changelog** | Collector + Policy | File parsing | 1 | CHANGELOG.md standards |
| 27 | **Dev container** | Collector + Policy | File parsing | 1 | .devcontainer config |
| 28 | **Renovate detailed** | Collector | File parsing | 2 | Deep Renovate analysis |

---

## Later (Requires Platform Support)

These items are blocked on platform-level features (e.g., GitLab App support, BitBucket App support). Build when the platform support ships.

| Item | Type | Blocked On | Notes |
|------|------|------------|-------|
| **GitLab collector** (VCS + CI security) | Collector | GitLab App support | Mirrors `github` collector: branch protection, merge request settings, repo config. Also parses `.gitlab-ci.yml` for CI security. |
| **GitLab CI agent integration** | Collector | GitLab App support | CI hook collectors for GitLab pipelines (equivalent to GHA CI agent). |
| **BitBucket collector** (VCS settings) | Collector | BitBucket App support | Branch permissions, PR settings, repo config. |
