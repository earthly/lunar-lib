# Collector and Policy Implementation Mapping

This document maps the implemented collectors and policies in `lunar-cronos` to:
1. The implementation strategies from `strategies.md`
2. The corresponding guardrail specifications from `guardrail-specs/`

---

## Summary

| Category | Collectors | Policies | Primary Strategies |
|----------|------------|----------|-------------------|
| Repository & Docs | `readme` | `readme` | Strategy 8 |
| Service Catalog | `backstage` | `backstage` | Strategy 8 |
| Containers | `dockerfile`, `docker-build` | `dockerfile`, `docker-build` | Strategy 8, Strategy 1/4 |
| Kubernetes | `k8s`, `helm`, `argocd` | `k8s` | Strategy 8 |
| Infrastructure | `terraform` | `terraform` | Strategy 8 |
| Security Scanning | `snyk-github-app`, `semgrep-github-app` | `sca` | Strategy 2, Strategy 3 |
| VCS & Tickets | `github-pr`, `jira` | `jira` | Strategy 10, Strategy 11 |
| Language | `golang` | – | Strategy 8 |
| CI/CD | `buildkite`, `ci-meta` | – | Strategy 1 |
| LLM Analysis | `claude` | – | Strategy 7 |
| Testing | `autotest` | `autotest` | Internal testing |

---

## Collectors

### `readme`
**Description:** Collects README file presence and line count.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Parses the repository for README.md file existence and counts lines

**Component JSON Paths:**
- `.repo.readme_exists` - Boolean indicating README presence
- `.repo.readme_num_lines` - Number of lines in README

---

### `dockerfile`
**Description:** Collects Dockerfile information including AST, base images, and labels.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Uses `dockerfile-json` to parse Dockerfiles into JSON AST
- Extracts base images and labels from each stage
- Processes files in parallel

**Component JSON Paths:**
- `.dockerfile.asts[]` - Array of Dockerfile ASTs with paths
- `.dockerfile.images_summary[]` - Base images per Dockerfile
- `.dockerfile.labels_summary[]` - Labels by stage per Dockerfile

---

### `k8s`
**Description:** Collects and validates Kubernetes manifest files.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Finds all YAML files in the repository
- Validates K8s manifests using `kubeconform`
- Converts manifests to JSON and stores contents
- Uses `parallel` for efficient processing

**Component JSON Paths:**
- `.k8s.descriptors[]` - Array of K8s manifest data
  - `.k8s_file_location` - File path
  - `.valid` - Boolean validation result
  - `.validation_error` - Error message if invalid
  - `.contents` - Parsed manifest as JSON

---

### `terraform`
**Description:** Collects and validates Terraform configuration, analyzing security properties.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Uses `hcl2json` to parse Terraform files to JSON
- Runs helper scripts to check:
  - Internet accessibility
  - WAF protection
  - Datastore deletion protection

**Component JSON Paths:**
- `.terraform.files[]` - Array of Terraform files with validity
- `.terraform.is_internet_accessible` - Boolean for public exposure
- `.terraform.has_waf_protection` - Boolean for WAF presence
- `.terraform.has_datastores` - Boolean for datastore presence
- `.terraform.has_datastore_protection` - Boolean for deletion protection
- `.terraform.unprotected_datastores` - List of unprotected resources

---

### `backstage`
**Description:** Collects and validates Backstage catalog-info.yaml files.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Parses YAML files looking for Backstage catalog entries (`apiVersion: backstage.io/v1alpha1`)
- Validates using `validate-entity` tool
- Processes files in parallel

**Component JSON Paths:**
- `.backstage.catalogs[]` - Array of catalog entries
  - `.catalog_location` - File path
  - `.catalog` - Parsed catalog JSON
  - `.valid` - Boolean validation result
  - `.validation_error` - Error message if invalid

---

### `helm`
**Description:** Collects and validates Helm charts.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Finds directories containing Chart.yaml
- Validates using `helm lint`
- Processes charts in parallel

**Component JSON Paths:**
- `.helm.charts[]` - Array of Helm chart data
  - `.chart_location` - Chart directory path
  - `.valid` - Boolean validation result
  - `.validation_error` - Error if invalid

---

### `snyk-github-app`
**Description:** Detects Snyk GitHub App check runs on PRs.

**Hook Type:** `code`

**Strategy:** **Strategy 2 (GitHub App Status Check Integration)** + **Strategy 3 (Meta-policy for main branch)**
- In PR context: Queries GitHub API for Snyk status checks, waits for completion
- On main branch: Queries Lunar DB to verify Snyk ran on recent PRs (meta-policy pattern)

**Component JSON Paths:**
- `.sca.snyk.github_app_results` - Snyk check results from GitHub
- `.sca.snyk.github_app_run_recently` - Boolean for recent PR runs
- `.sca.run` - Boolean indicating SCA ran

---

### `semgrep-github-app`
**Description:** Detects Semgrep GitHub App check runs on PRs.

**Hook Type:** `code`

**Strategy:** **Strategy 2 (GitHub App Status Check Integration)** + **Strategy 3 (Meta-policy for main branch)**
- In PR context: Queries GitHub API for Semgrep check runs, waits for completion
- On main branch: Queries Lunar DB to verify Semgrep ran on recent PRs

**Component JSON Paths:**
- `.sca.semgrep.github_app_results` - Semgrep check results from GitHub
- `.sca.semgrep.github_app_run_recently` - Boolean for recent PR runs
- `.sca.run` - Boolean indicating SCA ran

---

### `github-pr`
**Description:** Collects GitHub PR metadata from the GitHub API.

**Hook Type:** `code`

**Strategy:** **Strategy 11 (VCS Provider API Queries)**
- Queries GitHub API for PR details when in PR context
- Collects full PR response (title, description, labels, reviewers, etc.)

**Component JSON Paths:**
- `.github.is_pr` - Boolean indicating PR context
- `.github.pr` - Full PR metadata from GitHub API

---

### `jira`
**Description:** Collects Jira ticket metadata referenced in PR titles.

**Hook Type:** `code`

**Strategy:** **Strategy 10 (External Vendor API Integration)**
- Extracts ticket ID from PR title using configurable patterns
- Queries Jira API to fetch ticket metadata

**Component JSON Paths:**
- `.jira.ticket` - Full Jira ticket metadata

---

### `docker-build`
**Description:** Collects docker build command information from CI.

**Hook Type:** `ci-after-command` (pattern: `^docker.*build.*`)

**Strategy:** **Strategy 1 (CI Tool Execution Detection)** + **Strategy 4 (CI Command Modification)**
- Detects docker build commands in CI
- Checks for presence of `--label` flag and `git_sha` label
- (Commented code shows future support for auto-injecting labels)

**Component JSON Paths:**
- `.docker_build.builds[]` - Array of docker build command data
  - `.cmd` - Full command string
  - `.expected_git_sha` - Expected git SHA for traceability
  - `.has_label_flag` - Boolean for `--label` presence
  - `.has_git_sha_label` - Boolean for git SHA in labels

---

### `golang`
**Description:** Collects Go project information and linting results.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)** + **Strategy 5 (Auto-Running Scanners)**
- Checks for Go project files (go.mod, go.sum, vendor, goreleaser)
- Runs `golangci-lint` and collects results

**Component JSON Paths:**
- `.golang.files` - Object with Go file existence flags
- `.golang.linting` - Golangci-lint results
  - `.passed` - Boolean for lint success
  - `.config_exists` - Boolean for config presence
  - `.output` - Lint output
  - `.exit_code` - Exit code

---

### `argocd`
**Description:** Collects ArgoCD application definitions.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Parses YAML files for ArgoCD resources (`apiVersion: argoproj.io/v1alpha1`)

**Component JSON Paths:**
- `.argocd.applications[]` - Array of ArgoCD application definitions

---

### `buildkite`
**Description:** Collects and parses Buildkite pipeline configurations.

**Hook Type:** `code`

**Strategy:** **Strategy 8 (File Parsing and Schema Extraction)**
- Finds pipeline.yml files
- Parses to JSON for analysis

**Component JSON Paths:**
- `.buildkite.pipelines[]` - Array of Buildkite pipeline configs

---

### `ci-meta`
**Description:** Collects CI/CD command and job metadata.

**Hook Types:** `ci-before-command`, `ci-after-command`, `ci-before-job`

**Strategy:** **Strategy 1 (CI Tool Execution Detection)**
- Captures all CI commands with timing and environment
- Provides foundation for CI analysis

**Component JSON Paths:**
- `.ci.commands.<hash>` - Command metadata including start/end time and environment
- `.ci.before-job-env` - Environment variables at job start

---

### `claude`
**Description:** Runs Claude LLM prompts on the repository.

**Hook Type:** `code`

**Strategy:** **Strategy 7 (LLM-Assisted Analysis)**
- Executes configurable Claude prompts
- Stores results at configurable JSON path
- Requires `ANTHROPIC_API_KEY` secret

**Inputs:**
- `path` - JSON component path for results
- `prompt` - Claude prompt to run

---

### `autotest`
**Description:** Collects automated test value for internal testing.

**Hook Type:** `code`

**Strategy:** Internal testing mechanism

**Component JSON Paths:**
- `.autotest.value` - Test value from filesystem

---

## Policies

### `readme`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `readme-exists` | Repository should have a README.md file | Strategy 8 | `docs-readme-exists` from `repository-and-ownership.md` |

**Logic:** Asserts `.repo.readme_exists` is true.

---

### `dockerfile`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `dockerfile-no-latest` | Dockerfiles should not use the `:latest` tag | Strategy 8 | `container-specific-tag` from `devex-build-and-ci.md` |
| `dockerfile-labels` | Dockerfiles should have required labels | Strategy 8 | `container-oci-labels` from `devex-build-and-ci.md` |
| `dockerfile-allowed-registries` | Dockerfiles should only use images from allowed registries | Strategy 8 | `container-approved-base-images` from `devex-build-and-ci.md` |

**Inputs:**
- `requiredLabels` - Comma-separated list of required labels
- `allowedRegistries` - Comma-separated list of allowed registries (default: `docker.io`)

---

### `k8s`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `k8s-valid-config` | Valid K8s configuration | Strategy 8 | N/A (validation) |
| `k8s-pdb-per-workload` | PDB per workload | Strategy 8 | `k8s-pdb-exists` from `deployment-and-infrastructure.md` |
| `k8s-min-replicas` | Valid minReplicas in HPA | Strategy 8 | `k8s-hpa-min-replicas` from `deployment-and-infrastructure.md` |
| `k8s-resources` | Containers have CPU/Memory requests & limits | Strategy 8 | `k8s-container-has-cpu-memory-requests`, `k8s-container-has-cpu-memory-limits`, `k8s-cpu-limit-request-ratio` from `deployment-and-infrastructure.md` |

**Inputs:**
- `minReplicas` - Minimum replicas required for HPA
- `maxLimitToRequestRatio` - Maximum CPU/memory limit-to-request ratio (default: 4)

---

### `backstage`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `backstage-catalog-info-exists` | Backstage Config Exists | Strategy 8 | `catalog-registered` from `repository-and-ownership.md` |
| `backstage-catalog-info-valid` | Backstage Config is Valid | Strategy 8 | `catalog-valid-yaml` from `repository-and-ownership.md` |

---

### `terraform`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `terraform-valid` | Terraform configuration is valid | Strategy 8 | N/A (validation) |
| `terraform-has-waf` | Services deployed to the internet should have WAF protection | Strategy 8 | Related to `sec-apis-require-tls` and network security from `security-and-compliance.md` |
| `terraform-has-delete-protection` | Terraform services with datastores should have delete protection | Strategy 8 | `sec-db-encryption-at-rest` concepts from `security-and-compliance.md` (datastore protection) |

---

### `sca`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `sca` | SCA scanner should be run on each code change | Strategy 2 + Strategy 3 | `sec-sca-executed` from `security-and-compliance.md` |

**Logic:** Asserts `.sca.run` exists, which is set by `snyk-github-app` or `semgrep-github-app` collectors.

---

### `jira`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `jira-ticket-present` | Jira ticket must be present in PR | Strategy 10 + Strategy 11 | `vcs-commits-reference-ticket` from `security-and-compliance.md`, `vcs-pr-ticket-reference` from `repository-and-ownership.md` |

**Logic:** In PR context, asserts `.jira.ticket` exists.

---

### `docker-build`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `docker-build-git-sha` | Docker builds must include git SHA label | Strategy 1 + Strategy 4 | `container-git-sha-label`, `container-git-sha-traceable` from `devex-build-and-ci.md` |

---

### `autotest`
**Checks:**

| Check ID | Description | Strategy | Guardrail Spec |
|----------|-------------|----------|----------------|
| `autotest-value-matches` | Autotest value matches filesystem | N/A | Internal testing |

---

## Strategy Usage Summary

| Strategy | Description | Collectors | Policies |
|----------|-------------|------------|----------|
| **Strategy 1** | CI Tool Execution Detection | `docker-build`, `ci-meta` | `docker-build` |
| **Strategy 2** | GitHub App Status Check Integration | `snyk-github-app`, `semgrep-github-app` | `sca` |
| **Strategy 3** | Cross-Component and Historical Data Queries | `snyk-github-app`, `semgrep-github-app` (main branch) | `sca` |
| **Strategy 4** | CI Command Modification | `docker-build` (planned) | – |
| **Strategy 5** | Auto-Running Scanners | `golang` (golangci-lint) | – |
| **Strategy 7** | LLM-Assisted Analysis | `claude` | – |
| **Strategy 8** | File Parsing and Schema Extraction | `readme`, `dockerfile`, `k8s`, `terraform`, `backstage`, `helm`, `argocd`, `buildkite`, `golang` | `readme`, `dockerfile`, `k8s`, `backstage`, `terraform` |
| **Strategy 10** | External Vendor API Integration | `jira` | `jira` |
| **Strategy 11** | VCS Provider API Queries | `github-pr` | `jira` |

---

## Guardrail Spec Coverage

### Repository and Ownership (`repository-and-ownership.md`)
| Guardrail | Implemented | Collector | Policy |
|-----------|-------------|-----------|--------|
| `docs-readme-exists` | ✅ | `readme` | `readme` |
| `catalog-registered` | ✅ | `backstage` | `backstage` |
| `catalog-valid-yaml` | ✅ | `backstage` | `backstage` |
| `vcs-pr-ticket-reference` | ✅ | `jira`, `github-pr` | `jira` |

### Security and Compliance (`security-and-compliance.md`)
| Guardrail | Implemented | Collector | Policy |
|-----------|-------------|-----------|--------|
| `sec-sca-executed` | ✅ | `snyk-github-app`, `semgrep-github-app` | `sca` |
| `vcs-commits-reference-ticket` | ✅ | `jira`, `github-pr` | `jira` |

### Deployment and Infrastructure (`deployment-and-infrastructure.md`)
| Guardrail | Implemented | Collector | Policy |
|-----------|-------------|-----------|--------|
| `k8s-pdb-exists` | ✅ | `k8s` | `k8s` (`k8s-pdb-per-workload`) |
| `k8s-hpa-min-replicas` | ✅ | `k8s` | `k8s` (`k8s-min-replicas`) |
| `k8s-container-has-cpu-memory-requests` | ✅ | `k8s` | `k8s` (`k8s-resources`) |
| `k8s-container-has-cpu-memory-limits` | ✅ | `k8s` | `k8s` (`k8s-resources`) |
| `k8s-cpu-limit-request-ratio` | ✅ | `k8s` | `k8s` (`k8s-resources`) |

### DevEx, Build and CI (`devex-build-and-ci.md`)
| Guardrail | Implemented | Collector | Policy |
|-----------|-------------|-----------|--------|
| `container-specific-tag` | ✅ | `dockerfile` | `dockerfile` (`dockerfile-no-latest`) |
| `container-oci-labels` | ✅ | `dockerfile` | `dockerfile` (`dockerfile-labels`) |
| `container-approved-base-images` | ✅ | `dockerfile` | `dockerfile` (`dockerfile-allowed-registries`) |
| `container-git-sha-label` | ✅ | `docker-build` | `docker-build` |
| `container-git-sha-traceable` | ✅ | `docker-build` | `docker-build` |

---

## Collectors Without Corresponding Policies

The following collectors gather data but don't have dedicated policies yet:

| Collector | Data Collected | Potential Policies |
|-----------|---------------|-------------------|
| `golang` | Go project structure, linting results | Go linter passing, go.sum exists |
| `helm` | Helm chart validity | Helm charts must be valid |
| `argocd` | ArgoCD applications | ArgoCD apps configured correctly |
| `buildkite` | Pipeline configurations | CI pipeline requirements |
| `ci-meta` | CI command/job metadata | CI performance, required steps |
| `github-pr` | Full PR metadata | PR size limits, description requirements |
| `claude` | LLM analysis results | Custom LLM-based checks |
