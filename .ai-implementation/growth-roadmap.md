# Lunar-Lib Growth Roadmap: Next 50 Collectors & Policies

Prioritized plan for expanding lunar-lib with high-mass-appeal, free/OSS-friendly collectors and policies.

**Goal:** Build a library large enough that any new customer can select ~50 collectors and policies from it and get meaningful results immediately. There's a universal baseline (~30 items) that works for everyone out of the box, plus a conditional menu (~30+ more) that customers pick from based on their stack and practices.

**Audience:** AI agents (Devin, Cursor, etc.) picking up individual items to implement autonomously.

---

## Product Model: The "Starter Pack"

Every Lunar customer gets a **universal baseline** of ~30 items that "just works" — collectors skip gracefully when a technology isn't present, policies skip when underlying data is absent. No noise, no false positives for missing tech.

Customers then add **~20 more items** from the conditional menu based on their stack (Jira, PagerDuty, Snyk, etc.) to reach their ~50-item starter pack.

### Item classification:

- 🟢 **Universal** — Safe for every customer. Collectors skip if tech not detected; policies skip if data absent. Auto-enable for all accounts.
- 🟡 **Aspirational** — Universal in spirit (every company _should_ do this), fails intentionally when missing. In universal pack. All policies should be imported at `score` level initially; customers can promote to `report-pr` or `block-pr` later.
- 🔵 **Conditional** — Customer opts in based on their stack/practices.

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

## The Universal Starter Pack (~45 items)

This is what every customer gets on day one. Items marked 🆕 need to be built.

### Collectors (21)

| # | Plugin | Category | Class | Notes |
|---|--------|----------|-------|-------|
| 1 | `readme` | Repo health | 🟢 | Every repo |
| 2 | `codeowners` | Ownership | 🟢 | Every repo |
| 3 | `github` | VCS settings | 🟢 | Branch protection, repo settings |
| 4 | `docker` | Containers | 🟢 | Skips if no Dockerfiles |
| 5 | `k8s` | Infrastructure | 🟢 | Skips if no K8s manifests |
| 6 | `terraform` | Infrastructure | 🟢 | Skips if no `.tf` files |
| 7 | `syft` | SBOM | 🟢 | Auto-generates SBOM for any repo |
| 8 | `codecov` | Coverage | 🟢 | Skips if no coverage tool |
| 9 | `semgrep` | SAST | 🟢 | Detects Semgrep usage, skips if absent |
| 10 | `ast-grep` | Code patterns | 🟢 | Auto-runs pattern analysis |
| 11 | `golang` | Language | 🟢 | Skips if not Go |
| 12 | `java` | Language | 🟢 | Skips if not Java |
| 13 | `nodejs` | Language | 🟢 | Skips if not Node |
| 14 | `python` | Language | 🟢 | Skips if not Python |
| 15 | `rust` | Language | 🟢 | Skips if not Rust |
| 16 | 🆕 `php` | Language | 🟢 | Skips if not PHP |
| 17 | 🆕 `dotnet` | Language | 🟢 | Skips if not .NET |
| 18 | 🆕 `gitleaks` | Secret scanning | 🟢 | Auto-runs on every repo |
| 19 | 🆕 `trivy` | SCA + container | 🟢 | Auto-runs free vuln scanning |
| 20 | 🆕 `gha-security` | CI security | 🟢 | Skips if no `.github/workflows/` |
| 21 | 🆕 `api-docs` | API specs | 🟢 | Detects OpenAPI/Swagger specs, skips if none |

### Policies (24)

| # | Plugin | Checks in Universal Pack | Class | Notes |
|---|--------|--------------------------|-------|-------|
| 21 | 🆕 `repo-hygiene` | `readme-exists`, `readme-min-length`, `codeowners-exists`, `codeowners-valid`, `codeowners-catchall`, `gitignore-exists`, `license-exists`, `ci-config-exists` | 🟡 | Consolidates `readme` + `codeowners` + new standard file checks. Aspirational — fails intentionally when files missing. |
| 22 | `vcs` | Branch protection, approvals, no force push | 🟡 | Aspirational — you should have branch protection |
| 23 | `container` | Dockerfile best practices | 🟢 | Skips if no Dockerfiles |
| 24 | `container-scan` | No critical image vulns | 🟢 | Skips if no scan data |
| 25 | `k8s` | Resource limits, probes, PDBs | 🟢 | Skips if no K8s manifests |
| 26 | `terraform` | Provider pinning, state backend | 🟢 | Skips if no `.tf` files |
| 27 | `iac` | General IaC standards | 🟢 | Skips if no IaC data |
| 28 | `iac-scan` | No critical IaC misconfigs | 🟢 | Skips if no scan data |
| 29 | `sbom` | SBOM exists, license compliance | 🟢 | Skips if no SBOM data |
| 30 | `sast` | SAST scan executed | 🟢 | Skips if no SAST data |
| 31 | `sca` | No critical vulns | 🟢 | Skips if no SCA data |
| 32 | `dependencies` | Lock files, versions | 🟢 | Skips per language |
| 33 | `linter` | Lint configured | 🟢 | Skips if not detected |
| 34 | `testing` | `executed`, `passing` only | 🟢 | Skips if no `.lang.*`; coverage checks NOT in universal |
| 35 | `golang` | Go-specific checks | 🟢 | Skips if not Go |
| 36 | `java` | Java-specific checks | 🟢 | Skips if not Java |
| 37 | `nodejs` | Node-specific checks | 🟢 | Skips if not Node |
| 38 | `python` | Python-specific checks | 🟢 | Skips if not Python |
| 39 | `rust` | Rust-specific checks | 🟢 | Skips if not Rust |
| 40 | 🆕 `php` | PHP-specific checks | 🟢 | Skips if not PHP |
| 41 | 🆕 `dotnet` | .NET-specific checks | 🟢 | Skips if not .NET |
| 42 | 🆕 `secrets` | No secrets in code | 🟢 | On Gitleaks data; skips if no scan data |
| 43 | 🆕 `ci-security` | Pinned actions, minimal permissions | 🟢 | Skips if no GHA workflows |
| 44 | 🆕 `api-docs` | OpenAPI/Swagger spec exists, valid | 🟢 | Skips if no API spec detected; Swagger is ubiquitous |

### Planned change: `repo-hygiene` consolidation

When building the `repo-hygiene` policy, fold the existing `readme` and `codeowners` policies into it. The new policy includes all their existing checks plus:

- `gitignore-exists` — `.gitignore` file present
- `license-exists` — `LICENSE` or `LICENSE.md` present
- `ci-config-exists` — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, or similar
- `dockerignore-exists` — `.dockerignore` present when Dockerfiles exist (conditional check)

The existing `readme` and `codeowners` collector plugins remain separate (they collect different data). Only the policies merge.

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
| 🆕 `openssf` collector + policy | Supply chain scoring for auditors | +2 |
| 🆕 `pagerduty` + `oncall` policy | On-call verification | +2 |
| 🆕 `cosign` + `signing` policy | Image signing verification | +2 |
| **Total** | | **~61** |

**What the CISO gets:** Secret scanning, vulnerability scanning (Snyk + Trivy), SBOM + license compliance, IaC security (Checkov), supply chain scoring (OpenSSF Scorecard), branch protection, ticket traceability, DR docs, on-call verification, image signing. Pre-packaged SOC2/NIST controls. Regulated companies will often exceed ~50 because they need more controls.

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
| 🆕 `openssf` collector + policy | OSS project scoring | +2 |
| 🆕 `dependabot-renovate` collector + policy | Dep updates | +2 |
| 🆕 `cosign` + `signing` policy | Image signing | +2 |
| **Total** | | **~57** |

**What the Head of Platform gets:** Deep infrastructure coverage (K8s + Terraform + Helm validated at every commit), Go/Rust code quality and language-specific checks from universal, supply chain scoring for their OSS projects, image signing verification, operational readiness docs.

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
| P11 | **OpenSSF Scorecard collector + policy** | A, D | 2–3 |
| P12 | **SonarQube collector** | A | 2–3 |

**Phase 3: Expanding the conditional menu** (Batch 2–4 items)

Items 13–50 from the original batch lists. See detailed specs below.

---

## Detailed Specs: Phase 1 & 2 Items

### P1. Gitleaks — Secret Scanning

**Type:** Collector + Policy  
**Class:** 🟢 Universal  
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

### P2. Trivy — Container & Filesystem Vulnerability Scanning

**Type:** Collector (multi-sub-collector) + feeds existing policies  
**Class:** 🟢 Universal  
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

### P3. GitHub Actions Security — Workflow File Analysis

**Type:** Collector + Policy  
**Class:** 🟢 Universal (skips if no GHA)  
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

### P4. Repo Hygiene — Consolidated Standard File Checks

**Type:** Policy (consolidates existing `readme` + `codeowners` policies + new checks)  
**Class:** 🟡 Aspirational-Universal  
**Est. Dev Time:** 2–3 days  
**Tool:** None — uses existing collector data + file existence checks  
**Strategy:** Strategy 8 (File Parsing)

**What to build:**

A single `repo-hygiene` policy that replaces the separate `readme` and `codeowners` policies, adding new standard file checks:

- **Checks from existing `readme` policy:** `readme-exists`, `readme-min-length`, `readme-required-sections` (if applicable)
- **Checks from existing `codeowners` policy:** `codeowners-exists`, `codeowners-valid`, `codeowners-catchall`
- **New checks:**
  - `gitignore-exists` — `.gitignore` file present
  - `license-exists` — `LICENSE` or `LICENSE.md` present
  - `ci-config-exists` — `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`, or `buildkite/` detected
  - `dockerignore-exists` — `.dockerignore` present when Dockerfiles exist (conditional)
  - `security-md-exists` — `SECURITY.md` present (optional/aspirational)

**Data sources:** Reads from existing `.repo.readme.*`, `.ownership.codeowners.*`, and adds new file existence checks (may need minor collector changes or can use the existing `readme` collector's file scanning).

**Testing:**

- **Policy:** Test with various repos — one with all standard files → all PASS. One missing `.gitignore` → that check FAIL, others PASS. Repo with Dockerfiles but no `.dockerignore` → `dockerignore-exists` FAIL.
- **Migration:** Ensure the new policy produces identical results to the old `readme` and `codeowners` policies for their existing checks. Run both old and new against the same component JSON and compare.
- **No new collector needed** — the `readme` and `codeowners` collectors already gather the data. For `.gitignore`/`LICENSE` checks, either extend the `readme` collector (it already scans the repo root) or check file existence directly in the policy.

---

### P5. PHP Language Support

**Type:** Collector + Policy  
**Class:** 🟢 Universal (skip-safe)  
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
- **Collector:** Run on PHP project → verify composer.json parsing, dependency extraction. Run on Go project → verify nothing written.
- **Policy:** Feed JSON with PHP 8.2 (min 8.0) → PASS. Feed JSON with PHP 7.4 (EOL) → FAIL.
- **CI hook:** Add PHPUnit CI workflow, push to cronos, verify test results captured.

---

### P6. .NET/C# Language Support

**Type:** Collector + Policy  
**Class:** 🟢 Universal (skip-safe)  
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
- **Collector:** Run on .NET project → verify .csproj parsing, dependency extraction. Run on Python project → verify nothing written.
- **Policy:** Feed JSON with .NET 8 (minimum 6) → PASS. Feed JSON with .NET 5 (EOL) → FAIL.
- **CI hook:** Set up a GHA workflow with `dotnet test` on the test repo, push to cronos, verify CI collector captures test results.

---

### P7. API Documentation (OpenAPI/Swagger)

**Type:** Collector + Policy  
**Class:** 🟢 Universal (skips if no API spec detected)  
**Est. Dev Time:** 2 days  
**Tool:** None (YAML/JSON file detection and parsing)  
**Strategy:** Strategy 8 (File Parsing) — code hook

**What to build:**

- **Collector (code hook):** Find OpenAPI/Swagger spec files (`openapi.yaml`, `openapi.json`, `swagger.yaml`, `swagger.json`, `api-spec.*`). Validate syntax (valid YAML/JSON, has `openapi` or `swagger` key). Extract version, endpoint count, info metadata.
- **Policy checks:**
  - `api-spec-exists` — At least one API spec file found (skips if no spec-like files detected at all)
  - `api-spec-valid` — All found specs parse without errors

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
- **Policy:** Feed JSON with valid spec → PASS. Feed JSON with invalid spec → FAIL. Feed JSON with no `.api` key → SKIP.
- **Note:** Swagger (OpenAPI 2.0) is extremely common in legacy codebases. Supporting both Swagger 2.0 and OpenAPI 3.x is important for mass appeal. Start with Swagger/OpenAPI detection; we can add more API doc formats (GraphQL introspection, AsyncAPI, etc.) later.
- **No external dependencies** — pure shell + yq. Fast to develop.

---

### P8. Checkov — IaC Security Scanning

**Type:** Collector  
**Class:** 🔵 Conditional (IaC users)  
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

- **Collector:** Run on a repo with Terraform files → verify findings are detected. Run on repo with no IaC → verify nothing is written.
- **Policy integration:** Capture Checkov output → feed to existing `iac-scan` policy → verify pass/fail.
- **Docker image note:** Checkov is Python-based (~200MB). Needs its own image or a `security-scanners` image.
- **Important:** Check what the existing `iac-scan` policy expects as input paths. The Checkov collector must write data in the format the existing policy reads.

---

### P9. Helm Chart Support

**Type:** Collector + Policy  
**Class:** 🔵 Conditional (Helm users) — but skip-safe, could be universal  
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
- **Collector:** Run on chart → verify metadata extracted. Run on non-Helm repo → verify nothing written. Run `helm lint` → verify warnings captured.
- **Policy:** Feed JSON with clean chart → PASS. Feed JSON with deprecated API → FAIL. Feed JSON with no `.k8s.helm` → SKIP.
- **Docker image:** `helm` binary needs to be in the image. Small binary, easy to add.

---

### P10. Dependabot/Renovate — Dependency Update Automation

**Type:** Collector + Policy  
**Class:** 🔵 Conditional (aspirational — "you should have dep updates")  
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

### P11. OpenSSF Scorecard — Supply Chain Security Scoring

**Type:** Collector + Policy  
**Class:** 🔵 Conditional (enterprise/compliance-focused)  
**Est. Dev Time:** 2–3 days  
**Tool:** [OpenSSF Scorecard](https://github.com/ossf/scorecard) — free, backed by Google/OSSF  
**Strategy:** Strategy 5 (Auto-Running Scanners) — code hook or cron

**What to build:**

- **Collector:** Run `scorecard --repo=<component-url> --format=json`. Parses 18+ checks (branch protection, CI tests, dependency review, fuzzing, signed releases, etc.). Writes aggregate score and per-check results.
- **Policy checks:**
  - `scorecard-minimum-score` — Aggregate score ≥ configurable threshold (default: 5/10)
  - `scorecard-critical-checks` — Specific checks must pass (e.g., `Branch-Protection`, `Token-Permissions`)

**Testing:**

- **Collector:** Run against a public GitHub repo (e.g., `pantalasa-cronos/backend` if public). Scorecard requires repo to be on a supported platform (GitHub, GitLab) and may need `GITHUB_TOKEN` for rate limits.
- **Policy:** Feed JSON with score 7 (threshold 5) → PASS. Feed JSON with score 3 → FAIL.
- **Note:** Scorecard CLI needs network access to query GitHub API. This means it works as a `cron` collector or `code` collector with network. Test with `--local` flag where possible for offline testing.
- **Note:** Lunar already provides some of these checks natively (branch protection via `github` collector + `vcs` policy). The value of Scorecard is the industry-standard score that procurement teams ask for, plus checks we don't cover yet (signed releases, fuzzing, SAST).

---

### P12. SonarQube/SonarCloud Integration

**Type:** Collector  
**Class:** 🔵 Conditional (SonarQube users)  
**Est. Dev Time:** 2–3 days  
**Tool:** SonarCloud free tier (for testing) or status check detection  
**Strategy:** Strategy 2 (GitHub App Status Check) + Strategy 1 (CI Detection)

**What to build:**

- **Sub-collector `github-app`:** Detect SonarCloud GitHub App status checks on PRs (like semgrep/snyk pattern). Extract quality gate status.
- **Sub-collector `cicd`:** Detect `sonar-scanner` or `sonarqube` CLI execution in CI. Extract analysis results.
- **Feeds:** Existing `sast` policy (code quality findings) and `testing` policy (coverage metrics from SonarQube)

**Testing:**

- **GitHub App sub-collector:** Install SonarCloud free tier on a `pantalasa-cronos` public repo. Open a PR → verify status check is detected and parsed.
- **CI sub-collector:** Add a SonarScanner step to a GHA workflow → verify CI detection.
- **Note:** SonarCloud is free for open-source repos. For testing, fork a public repo to `pantalasa-cronos` and connect SonarCloud to it.
- **Follows the exact same pattern as `semgrep` and `snyk` collectors** — use those as templates.

---

## Remaining Batch Items (Phase 3)

### Batch 2: Items 13–25 (High Impact)

| # | Item | Type | Tool/Strategy | Est. Days | Mass Appeal | Notes |
|---|------|------|---------------|-----------|-------------|-------|
| 13 | **GitLab CI security** | Collector + Policy | File parsing `.gitlab-ci.yml` | 2–3 | 8/10 | Same concept as P3 but for GitLab. Parse for image pinning, secret exposure. |
| 14 | **Backstage catalog-info.yaml** | Collector + Policy | File parsing `catalog-info.yaml` | 2 | 8/10 | Service catalog standard. Check entity fields, annotations, dependencies. |
| 15 | **PagerDuty on-call** | Collector + Policy | PagerDuty API (free tier available) | 3 | 7/10 | Verify on-call schedules, min participants, escalation. |
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
