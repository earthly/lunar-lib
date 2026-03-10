# Lunar-Lib Growth Roadmap: Next 50 Collectors & Policies

Prioritized plan for expanding lunar-lib with high-mass-appeal, free/OSS-friendly collectors and policies.

**Goal:** Build a library large enough that any new customer can select ~50 collectors and policies from it and get meaningful results immediately. There's a universal baseline (~30 items) that works for everyone out of the box, plus a conditional menu (~30+ more) that customers pick from based on their stack and practices.

**Audience:** AI agents (Devin, Cursor, etc.) picking up individual items to implement autonomously.

---

## Product Model: The "Starter Pack"

Every Lunar customer gets a **universal baseline** (~45 items) that provides a solid foundation for any initial installation and should be safe to run on any account. Collectors skip gracefully when a technology isn't present, and policies skip when underlying data is absent — no noise, no false positives for missing tech. Baseline items can also be removed if a customer doesn't want them, but they're designed to "just work" out of the box.

Customers then add items from the **conditional menu** based on their stack (Jira, PagerDuty, Snyk, etc.) to reach their ~50-item starter pack. All policies should be imported at `score` level initially; customers can promote to `report-pr` or `block-pr` later.

---

## Current Inventory (as of March 2026)

**21 collectors:** ai-use, ast-grep, ci-otel, claude, codecov, codeowners, docker, dr-docs, github, golang, java, jira, k8s, nodejs, python, readme, rust, semgrep, snyk, syft, terraform

**24 policies:** ai-use, codeowners, compliance-docs, container, container-scan, dependencies, feature-flags, golang, iac, iac-scan, java, k8s, linter, nodejs, python, readme, rust, sast, sbom, sca, terraform, testing, ticket, vcs

---

## The Universal Starter Pack (~45 items)

This is what every customer gets on day one. Items marked 🆕 need to be built.

### Collectors (21)

| # | Plugin | Category | Notes |
|---|--------|----------|-------|
| 1 | `readme` | Repo health | Every repo |
| 2 | `codeowners` | Ownership | Every repo |
| 3 | `github` | VCS settings | Branch protection, repo settings |
| 4 | `docker` | Containers | Skips if no Dockerfiles |
| 5 | `k8s` | Infrastructure | Skips if no K8s manifests |
| 6 | `terraform` | Infrastructure | Skips if no `.tf` files |
| 7 | `syft` | SBOM | Auto-generates SBOM for any repo |
| 8 | `semgrep` | SAST | Detects Semgrep usage, skips if absent |
| 9 | `ast-grep` | Code patterns | Auto-runs pattern analysis |
| 10 | `golang` | Language | Skips if not Go |
| 11 | `java` | Language | Skips if not Java |
| 12 | `nodejs` | Language | Skips if not Node |
| 13 | `python` | Language | Skips if not Python |
| 14 | `rust` | Language | Skips if not Rust |
| 15 | 🆕 `php` | Language | Skips if not PHP |
| 16 | 🆕 `dotnet` | Language | Skips if not .NET |
| 17 | 🆕 `gitleaks` | Secret scanning | Auto-runs on every repo |
| 18 | 🆕 `trivy` | SCA + container | Auto-runs free vuln scanning |
| 19 | 🆕 `gha-security` | CI security | Skips if no `.github/workflows/` |
| 20 | 🆕 `api-docs` | API specs | Detects OpenAPI/Swagger specs, skips if none |
| 21 | 🆕 `repo-hygiene` | Repo health | Scans for standard files (.gitignore, LICENSE, CI config, .dockerignore, SECURITY.md, CONTRIBUTING.md, .editorconfig) |

### Policies (24)

| # | Plugin | Checks in Universal Pack | Notes |
|---|--------|--------------------------|-------|
| 22 | 🆕 `repo-hygiene` | `readme-exists`, `readme-min-length`, `codeowners-exists`, `codeowners-valid`, `codeowners-catchall`, `gitignore-exists`, `license-exists`, `ci-config-exists`, `dockerignore-exists`, `security-md-exists`, `contributing-md-exists`, `editorconfig-exists` | Consolidates `readme` + `codeowners` + new standard file checks. Uses data from `repo-hygiene` collector. |
| 23 | `vcs` | Branch protection, approvals, no force push | You should have branch protection |
| 24 | `container` | Dockerfile best practices | Skips if no Dockerfiles |
| 25 | `container-scan` | No critical image vulns | Skips if no scan data |
| 26 | `k8s` | Resource limits, probes, PDBs | Skips if no K8s manifests |
| 27 | `terraform` | Provider pinning, state backend | Skips if no `.tf` files |
| 28 | `iac` | General IaC standards | Skips if no IaC data |
| 29 | `iac-scan` | No critical IaC misconfigs | Skips if no scan data |
| 30 | `sbom` | SBOM exists, license compliance | Skips if no SBOM data |
| 31 | `sast` | SAST scan executed | Skips if no SAST data |
| 32 | `sca` | No critical vulns | Skips if no SCA data |
| 33 | `dependencies` | Lock files, versions | Skips per language |
| 34 | `linter` | Lint configured | Skips if not detected |
| 35 | `testing` | `executed`, `passing` only | Skips if no `.lang.*`; coverage checks NOT in universal |
| 36 | `golang` | Go-specific checks | Skips if not Go |
| 37 | `java` | Java-specific checks | Skips if not Java |
| 38 | `nodejs` | Node-specific checks | Skips if not Node |
| 39 | `python` | Python-specific checks | Skips if not Python |
| 40 | `rust` | Rust-specific checks | Skips if not Rust |
| 41 | 🆕 `php` | PHP-specific checks | Skips if not PHP |
| 42 | 🆕 `dotnet` | .NET-specific checks | Skips if not .NET |
| 43 | 🆕 `secrets` | No secrets in code | On Gitleaks data; skips if no scan data |
| 44 | 🆕 `ci-security` | Pinned actions, minimal permissions | Skips if no GHA workflows |
| 45 | 🆕 `api-docs` | OpenAPI/Swagger spec exists, valid | Skips if no API spec detected |

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

## Conditional Menu (~30+ items)

Customers pick from this list based on their stack to reach ~50 total.

**Vendor integrations:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C1 | `jira` collector + `ticket` policy | Both | Uses Jira |
| C2 | `snyk` collector | Collector | Uses Snyk |
| C3 | 🆕 `sonarqube` collector | Collector | Uses SonarQube/SonarCloud |
| C4 | 🆕 `pagerduty` collector + `oncall` policy | Both | Uses PagerDuty |
| C5 | 🆕 `opsgenie` collector + `oncall` policy | Both | Uses OpsGenie |
| C6 | 🆕 `backstage` collector + `catalog` policy | Both | Uses Backstage |
| C7 | 🆕 `datadog` collector + `observability` policy | Both | Uses Datadog |
| C8 | 🆕 `grafana` collector + `observability` policy | Both | Uses Grafana |
| C9 | 🆕 `linear` collector + `ticket` policy | Both | Uses Linear |

**Security & compliance:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C10 | 🆕 `openssf` collector + policy | Both | Wants supply chain scoring |
| C11 | 🆕 `checkov` collector | Collector | Uses IaC (enhances `iac-scan`) |
| C12 | 🆕 `owasp-zap` collector | Collector | Wants DAST scanning |
| C13 | 🆕 `cosign` collector + `signing` policy | Both | Wants image signing verification |
| C14 | `compliance-docs` + `dr-docs` | Both | Needs compliance/DR documentation |

**Testing & quality:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C15 | `testing` policy (coverage checks) | Policy | Wants coverage enforcement (`coverage-collected`, `min-coverage`) |
| C16 | 🆕 `code-complexity` collector + policy | Both | Wants McCabe/cognitive complexity limits |

**Infrastructure & deployment:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C17 | 🆕 `helm` collector + policy | Both | Uses Helm |
| C18 | 🆕 `argocd-flux` collector + `gitops` policy | Both | Uses GitOps deployment |
| C19 | 🆕 `cloudformation` collector | Collector | Uses AWS CloudFormation |
| C20 | 🆕 `pulumi` collector | Collector | Uses Pulumi |

**Dependency management:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C21 | 🆕 `dependabot-renovate` collector + policy | Both | Wants dep update tracking |
| C22 | 🆕 `endoflife` collector + policy | Both | Wants runtime/framework EOL checking |

**DevEx & practices:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C23 | `feature-flags` policy | Policy | Uses feature flags |
| C24 | `ai-use` collector + policy | Both | Wants AI governance |
| C25 | 🆕 `pre-commit` collector + policy | Both | Wants pre-commit hook enforcement |
| C26 | 🆕 `editorconfig` collector + policy | Both | Wants formatting consistency |
| C27 | 🆕 `docker-compose` collector + policy | Both | Wants local dev environment checks |

**CI platforms (beyond GHA):**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C28 | 🆕 `gitlab-ci` collector | Collector | Uses GitLab CI |
| C29 | 🆕 `jenkins` collector | Collector | Uses Jenkins |
| C30 | 🆕 `circleci` collector | Collector | Uses CircleCI |
| C31 | 🆕 `azure-devops` collector | Collector | Uses Azure DevOps |
| C32 | 🆕 `buildkite` collector | Collector | Uses Buildkite |

**Specialized:**

| # | Item | Type | Trigger |
|---|------|------|---------|
| C33 | `ci-otel` | Collector | Wants OpenTelemetry CI traces |
| C34 | `claude` | Collector | Wants LLM-assisted code analysis |
| C35 | 🆕 `ruby` collector + policy | Both | Uses Ruby/Rails |
| C36 | 🆕 `swift-kotlin` collector | Collector | Mobile development |

---

## Example 50-Packs by Company Type

### Pack A: Regulated Enterprise (Fintech / Healthcare / Gov)

**Profile:** 500+ engineers. Java/.NET/Go. K8s + Terraform + Helm. Snyk + SonarQube. Jira. PagerDuty. SOC2/PCI/HIPAA.

| Source | Items | Count |
|--------|-------|-------|
| Universal baseline | All 45 | 45 |
| `jira` collector + `ticket` policy | Ticket traceability | +2 |
| `snyk` collector | Enterprise SCA | +1 |
| `testing` (coverage checks) | `coverage-collected`, `min-coverage` | +1 |
| `compliance-docs` + `dr-docs` | DR plan compliance | +2 |
| 🆕 `checkov` collector | IaC security scanning | +1 |
| 🆕 `sonarqube` collector | Code quality gate | +1 |
| 🆕 `helm` collector + policy | Helm chart validation | +2 |
| 🆕 `pagerduty` + `oncall` policy | On-call verification | +2 |
| 🆕 `cosign` + `signing` policy | Image signing verification | +2 |
| 🆕 `dependabot-renovate` collector + policy | Dep update tracking | +2 |
| **Total** | | **~61** |

**What the CISO gets:** Secret scanning, vulnerability scanning (Snyk + Trivy), SBOM + license compliance, IaC security (Checkov), branch protection, ticket traceability, DR docs, on-call verification, image signing. Pre-packaged SOC2/NIST controls. Regulated companies will often exceed ~50 because they need more controls.

---

### Pack B: AI-Native Startup

**Profile:** 30–80 engineers. Python-heavy + TypeScript/Go. Docker but no K8s (managed services). GHA. Linear (not Jira). Fast-moving, AI-heavy.

| Source | Items | Count |
|--------|-------|-------|
| Universal baseline | All 45 | 45 |
| `ai-use` collector + policy | AI governance | +2 |
| `feature-flags` policy | Flag hygiene | +1 |
| 🆕 `dependabot-renovate` collector + policy | Dep update tracking | +2 |
| 🆕 `linear` collector + `ticket` policy | Linear ticket refs | +2 |
| **Total** | | **~52** |

**What the CTO gets:** The universal baseline alone delivers massive value — secret scanning, free SCA (Trivy), SAST, API docs, language-specific checks for Python/Node/Go, testing enforcement. The conditional adds are lightweight: AI governance, feature flag tracking, dependency freshness, and Linear ticket references. They'll add K8s and compliance items as they grow.

---

### Pack C: E-Commerce SaaS

**Profile:** 150–300 engineers. Node.js + PHP (legacy) + Python. Docker + K8s. Terraform. GHA. Jira. Datadog.

| Source | Items | Count |
|--------|-------|-------|
| Universal baseline | All 45 | 45 |
| `jira` collector + `ticket` policy | Ticket references | +2 |
| `snyk` collector | Paid SCA | +1 |
| `testing` (coverage checks) | Coverage enforcement | +1 |
| `feature-flags` policy | Feature flag hygiene | +1 |
| 🆕 `checkov` collector | IaC scanning | +1 |
| 🆕 `helm` collector + policy | Helm charts | +2 |
| 🆕 `dependabot-renovate` collector + policy | Dep updates | +2 |
| 🆕 `endoflife` collector + policy | Runtime EOL (PHP 7!) | +2 |
| 🆕 `datadog` collector + `observability` policy | Dashboard verification | +2 |
| **Total** | | **~59** |

**What the VP Eng gets:** Full polyglot coverage (Node + PHP + Python + Go all covered by universal), K8s + Terraform safety nets, Jira traceability, coverage enforcement. The endoflife checker catches neglected legacy PHP services. Datadog integration verifies monitoring dashboards exist.

---

### Pack D: Platform / Infrastructure Company

**Profile:** 80–200 engineers. Go + Rust primary. Heavy Docker, K8s, Terraform, Helm. GHA or Buildkite. Open-source projects.

| Source | Items | Count |
|--------|-------|-------|
| Universal baseline | All 45 | 45 |
| `compliance-docs` + `dr-docs` | Ops maturity | +2 |
| `feature-flags` policy | Flag lifecycle | +1 |
| 🆕 `checkov` collector | IaC scanning | +1 |
| 🆕 `helm` collector + policy | Helm validation | +2 |
| 🆕 `dependabot-renovate` collector + policy | Dep updates | +2 |
| 🆕 `cosign` + `signing` policy | Image signing | +2 |
| 🆕 `pre-commit` collector + policy | Pre-commit hook enforcement | +2 |
| **Total** | | **~57** |

**What the Head of Platform gets:** Deep infrastructure coverage (K8s + Terraform + Helm validated at every commit), Go/Rust code quality and language-specific checks from universal, image signing verification, operational readiness docs, pre-commit hook enforcement for code quality gates.

---

## Implementation Priorities (Build Order)

Based on the starter pack model, the build order is:

**Phase 1: Complete the universal baseline** (items needed to ship the starter pack)

| Priority | Item | Why | Est. Days |
|----------|------|-----|-----------|
| P1 | **Gitleaks collector + secrets policy** | Fills biggest schema gap, every repo benefits | 2–3 |
| P2 | **Trivy collector** (filesystem + config) | Free SCA + container scan for everyone | 3–4 |
| P3 | **GHA security collector + ci-security policy** | Supply chain security, ~65% of market uses GHA | 2–3 |
| P4 | **repo-hygiene policy** | Consolidates readme + codeowners + new checks (.gitignore, LICENSE, CI config) | 2–3 |
| P5 | **PHP collector + policy** | Language detection, universal/skip-safe | 2–3 |
| P6 | **.NET/C# collector + policy** | Language detection, universal/skip-safe | 3–4 |
| P7 | **API docs collector + policy** | Swagger/OpenAPI detection, universal/skip-safe | 2 |

**Phase 2: Most popular conditional items** (appear in 3+ example packs)

| Priority | Item | Packs Using It | Est. Days |
|----------|------|----------------|-----------|
| P8 | **Checkov collector** | A, C, D | 2–3 |
| P9 | **Helm collector + policy** | A, C, D | 2–3 |
| P10 | **Dependabot/Renovate collector + policy** | B, C, D | 1.5–2 |
| P11 | **SonarQube collector** | A | 2–3 |
| P12 | **PagerDuty collector + oncall policy** | A | 3 |

**Phase 3: Expanding the conditional menu**

Items from the conditional menu above, prioritized by customer demand.

---

## Remaining Batch Items (Phase 3)

### Batch 2: Items 13–25 (High Impact)

| # | Item | Type | Tool/Strategy | Est. Days | Mass Appeal | Notes |
|---|------|------|---------------|-----------|-------------|-------|
| 13 | **GitLab CI security** | Collector + Policy | File parsing `.gitlab-ci.yml` | 2–3 | 8/10 | Same concept as P3 but for GitLab. Parse for image pinning, secret exposure. |
| 14 | **Backstage catalog-info.yaml** | Collector + Policy | File parsing `catalog-info.yaml` | 2 | 8/10 | Service catalog standard. Check entity fields, annotations, dependencies. |
| 15 | **OpenSSF Scorecard** | Collector + Policy | scorecard CLI (free, OSS) | 2–3 | 5/10 | Supply chain scoring. Niche but valued in compliance/procurement contexts. Needs network access. |
| 16 | **Datadog/Grafana dashboards** | Collector + Policy | Vendor API | 3 | 7/10 | Verify monitoring dashboards exist per service. |
| 17 | **OWASP ZAP** | Collector | ZAP CLI (free, OSS) | 3 | 7/10 | Dynamic security scanning for web apps. |
| 18 | **Gradle** (enhance Java) | Collector | File parsing `build.gradle` | 2 | 7/10 | Gradle-specific build parsing. |
| 19 | **Code complexity** | Collector + Policy | radon (Python), gocyclo (Go) | 2 | 7/10 | McCabe/cognitive complexity. |
| 20 | **Makefile/build-script** | Collector + Policy | File parsing | 1.5 | 7/10 | Check for `make build/test/lint` targets. |
| 21 | **Pre-commit hooks** | Collector + Policy | File parsing | 1.5 | 6/10 | Detect `.pre-commit-config.yaml`, husky, lefthook. |
| 22 | **EditorConfig + formatter** | Collector + Policy | File parsing | 1 | 6/10 | `.editorconfig`, prettier, black config exists. |
| 23 | **Docker Compose** | Collector + Policy | File parsing | 1.5 | 6/10 | `docker-compose.yml` for local dev. |
| 24 | **GitHub repo settings expansion** | Collector | GitHub API | 2 | 7/10 | Topics, visibility, description, vulnerability alerts. |
| 25 | **endoflife.date EOL checking** | Collector + Policy | endoflife.date API (free) | 2–3 | 8/10 | Cross-reference runtime/framework versions. |

### Batch 3: Items 26–38 (Broader Platform Coverage)

| # | Item | Type | Tool/Strategy | Est. Days | Notes |
|---|------|------|---------------|-----------|-------|
| 26 | **OpsGenie on-call** | Collector + Policy | OpsGenie API | 3 | Alternative to PagerDuty. |
| 27 | **Ruby language support** | Collector + Policy | File parsing + CI detection | 3 | Parse Gemfile, detect RSpec/Minitest. |
| 28 | **Swift/Kotlin mobile** | Collector | File parsing | 3 | Mobile app coverage. |
| 29 | **CloudFormation** | Collector | File parsing | 2 | AWS-native IaC. |
| 30 | **Pulumi** | Collector | File parsing | 2 | Modern IaC alternative. |
| 31 | **ArgoCD/Flux GitOps** | Collector + Policy | File parsing | 2 | GitOps deployment detection. |
| 32 | **Cosign image signing** | Collector + Policy | cosign CLI (free) | 2 | Container image signing verification. |
| 33 | **Renovate detailed** | Collector | File parsing | 2 | Deep Renovate config analysis. |
| 34 | **BitBucket support** | Collector | BitBucket API | 3 | Third major git platform. |
| 35 | **Jenkins pipeline** | Collector | File parsing `Jenkinsfile` | 2 | Still very common in enterprise. |
| 36 | **CircleCI** | Collector | File parsing `.circleci/config.yml` | 2 | Popular hosted CI. |
| 37 | **Azure DevOps** | Collector | File parsing + API | 3 | Major enterprise CI/CD. |
| 38 | **Buildkite** | Collector | File parsing `.buildkite/pipeline.yml` | 2 | Modern CI. |

### Batch 4: Items 39–50 (Specialized but Valuable)

| # | Item | Type | Tool/Strategy | Est. Days | Notes |
|---|------|------|---------------|-----------|-------|
| 39 | **Terraform Cloud/Spacelift** | Collector | Vendor API | 3 | IaC platform-level data. |
| 40 | **AWS CDK** | Collector | File parsing | 2 | Programmatic IaC. |
| 41 | **SLSA provenance** | Policy | Uses existing data | 1.5 | Supply chain attestation. |
| 42 | **OpenAPI linting (Spectral)** | Collector + Policy | Spectral CLI (free) | 2 | API quality. |
| 43 | **Database migration tracking** | Collector + Policy | File parsing | 2 | Flyway, Alembic, Liquibase. |
| 44 | **Changelog** | Collector + Policy | File parsing | 1 | CHANGELOG.md standards. |
| 45 | **Dev container** | Collector + Policy | File parsing | 1 | `.devcontainer` configuration. |
| 46 | **Grafana alerting rules** | Collector | Grafana API | 2 | Alert rule verification. |
| 47 | **Linear/GitHub Issues** | Collector | API | 2 | Expand ticket tracking beyond Jira. |
| 48 | **Runtime EOL via endoflife.date** | Collector | endoflife.date API | 2 | Language runtime EOL checking. |
| 49 | **Ruby** | Collector + Policy | File parsing | 2 | Ruby/Rails support. |
| 50 | **Gradle detailed** | Collector | File parsing | 2 | Gradle-specific enhancements. |

