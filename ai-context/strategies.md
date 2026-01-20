# Collector and Policy Implementation Strategies

This document describes common implementation strategies for building collectors and policies to satisfy the guardrail specifications.

---

## Strategy 1: CI Tool Execution Detection

Detect when a binary or tool runs in CI and optionally extract additional information about its results.

**How it works:**
* Use a CI collector (hook type `ci-after-command`) to detect when a specific binary has run.
* Optionally run a helper command to extract more information about the activity. Examples:
  * Version of the binary
  * Results of execution (e.g., after `npm install`, fetch list of installed packages)
  * Reports or artifacts produced (e.g., coverage reports, scan results)
* Record the binary name, version, and extracted data in the Component JSON.

**What policies can assert:**
* The tool has run (object presence check)
* The tool version meets requirements
* The results meet thresholds (e.g., no critical vulnerabilities, coverage above minimum)

---

## Strategy 2: GitHub App Status Check Integration

Detect when a GitHub App has run on PRs and optionally query the vendor's API for detailed results.

**How it works:**
* Use a code collector to query the GitHub API for PR check statuses. Implement busy-waiting with exponential back-off to wait for checks to complete.
* Record GitHub's status data (status, conclusion, details URL, etc.).
* Optionally query the vendor's API using identifiers from the status (scan ID, run ID, PR number, or Git SHA) to fetch detailed results.

**What policies can assert:**
* The GitHub App has run on PRs
* The check completed with expected status
* Detailed results meet requirements (e.g., no new critical vulnerabilities)

**Important consideration:** Some GitHub Apps only run on PRs, not the main branch. For main-branch enforcement, create a meta-policy that queries recent PR data to verify the app runs consistently. See Strategy 3.

---

## Strategy 3: Cross-Component and Historical Data Queries

Query Lunar's SQL API to make assertions based on data from other contexts (other PRs, historical SHAs, related components).

**How it works:**
* Use the Lunar SQL API within a policy to query Component JSONs from other contexts.
* Aggregate or compare data across multiple sources.

**What policies can assert:**
* **PR validation on main branch:** Verify that recent PRs have required checks (e.g., scanner ran on all PRs in the last 30 days)
* **Deployment freshness:** Confirm deployment occurred within the last X days
* **Dependency compliance:** Verify that upstream dependencies meet requirements
* **Trend analysis:** Ensure metrics haven't regressed compared to previous measurements

---

## Strategy 4: CI Command Modification

Intercept and modify CI commands before execution to add instrumentation or enforce standards.

**How it works:**
* Use a CI collector with hook type `ci-before-command` to detect when a specific command is about to run.
* Modify the command string or environment variables to:
  * Add automatic fixes (e.g., auto-tag Docker builds with Git SHA if missing)
  * Inject additional flags to produce more output (e.g., coverage report in a specific format)
  * Enable instrumentation or tracing

**What policies can assert:**
* Modified behavior was applied (via data collected post-execution)
* Required labels or tags are present on artifacts

---

## Strategy 5: Auto-Running Scanners

Automatically run security or quality scanners as part of Lunar's collection process.

**How it works:**
* Use a code collector to execute scanners directly (e.g., Snyk CLI, Semgrep, Trivy, Gitleaks).
* Parse and normalize the scanner output.
* Record results in the Component JSON.

**What policies can assert:**
* Scanner was executed (object presence)
* Results meet thresholds (no critical findings, all fixable, etc.)

**Advantages:** Works even if the team hasn't configured the scanner themselves. Provides consistent scanning across all components.

---

## Strategy 6: Advisory Guidance To Install/Enable Required Tool When Data is Missing

Provide actionable guidance when a policy cannot pass because required data doesn't exist.

**How it works:**
* When a policy evaluates and finds required data missing, provide a helpful failure message explaining:
  * What data is expected
  * How to install/enable the required app or tool
  * Links to documentation

**Example:**
* Policy: "No critical vulnerabilities found"
* Missing data: `.sca` object doesn't exist
* Message: "No SCA scanner detected. Configure Snyk or run `npm audit` in your CI pipeline. See: [docs link]"

---

## Strategy 7: LLM-Assisted Analysis (Claude Plugin)

Use Claude for analysis tasks that are difficult to automate with traditional pattern matching.

**How it works:**
* Lunar's Claude plugin can execute free-form prompts against the codebase.
* Results are recorded in the Component JSON as structured data.

**What Claude can detect:**
* Feature flags and their usage patterns across the codebase
* Publicly exposed APIs and their documentation quality
* SIGTERM/graceful shutdown handling in application code
* Required sections in markdown documents (runbooks, READMEs)
* Architecture patterns and anti-patterns

**What policies can assert:**
* All feature flags are documented or follow a naming convention
* All public APIs have adequate documentation
* Runbooks contain required information
* Graceful shutdown is properly implemented

**When to use:** When pattern-based detection is insufficient or would require complex language-specific parsing.

---

## Strategy 8: File Parsing and Schema Extraction

Parse files of specific types, convert to JSON, validate, and extract structured data for policy evaluation.

**How it works:**
* Use a code collector to find files matching patterns (Dockerfile, *.yaml, *.tf, CODEOWNERS, etc.).
* Validate file syntax using appropriate parsers or validators.
* Convert contents to normalized JSON structure. Conversion methods include:
  * YAML → JSON
  * HCL (Terraform) → JSON
  * CODEOWNERS → JSON (use an open-source CODEOWNERS parser)
  * Dockerfile → JSON (use an open-source Dockerfile to AST parser)
  * AST extraction via language-specific tools
* Use the `parallel` utility for efficient processing when many files exist.
* Perform any analysis needed for normalized data (e.g. extract Dockerfile base images)
* Store native and/or normalized data in the Component JSON.

**What policies can assert:**
* File exists in expected location
* File syntax is valid
* Semantic requirements are met (e.g., K8s manifests have resource limits, Dockerfiles don't use `latest` tag)

---

## Strategy 9: Manual Process Documentation Verification

Verify that required manual processes (DR drills, security reviews, etc.) are documented with timestamps.

**How it works:**
* Establish a convention for documenting manual processes in each repository (e.g., `docs/compliance/dr-drill.md`).
* Required documentation includes:
  * Timestamp of last execution
  * Summary of what was done
  * Approver sign-off (optional)
* A code collector reads the documentation files and extracts structured data.

**What policies can assert:**
* Documentation exists
* Last execution timestamp is within required timeframe (e.g., last 90 days)
* Required sections are present
* Approver is from authorized list (if required)

---

## Strategy 10: External Vendor API Integration

Query external vendor APIs to collect operational data not available in the repository.

**How it works:**
* Use a cron collector (for scheduled checks) or code collector (for code-change-triggered checks) to query vendor APIs.
* Authenticate using secrets managed by Lunar.
* Normalize vendor-specific responses to standard Component JSON structures.

**Data sources and examples:**
* **PagerDuty/OpsGenie:** On-call schedule participants, escalation policy levels
* **Jira/Linear:** Ticket existence and status validation
* **Grafana/Datadog:** Dashboard existence, alert configuration
* **HRIS systems (Workday, BambooHR):** Validate that CODEOWNERS are active employees
* **endoflife.date:** Dependency EOL status

**What policies can assert:**
* On-call rotation has minimum participants
* Referenced tickets exist and are valid
* Required dashboards and alerts are configured
* Team members are active employees

---

## Strategy 11: VCS Provider API Queries

Query the VCS provider (GitHub, GitLab, Bitbucket) API for repository configuration and branch settings.

**How it works:**
* Use a cron collector to query the VCS API for repository settings.
* Extract branch protection rules, access permissions, and repository metadata.
* Record settings in the Component JSON.

**Data to collect:**
* Branch protection settings (required approvals, status checks, force push restrictions)
* Repository visibility (public, private, internal)
* Topics/tags
* Default branch name
* Commit signing requirements
* Access permissions (who can push, who can merge)
* Allowed merge strategies (merge, squash, rebase)

**What policies can assert:**
* Branch protection is enabled with required settings
* Minimum approvals are required
* CODEOWNER review is required
* Force push is disabled
* Repository visibility matches requirements
* Correlation of access list with other systems like HRIS

---

## Strategy 12: Dependency Manifest Analysis

Analyze the dependency graph for security, licensing, and freshness using one of two approaches.

### Approach A: Direct Manifest Parsing

Parse dependency manifests and lock files directly to extract dependency information.

**How it works:**
* Use a code collector to find and parse dependency manifests (package.json, go.mod, requirements.txt, pom.xml, etc.) and lock files.
* Extract the full dependency list with versions.
* Cross-reference against external data sources:
  * endoflife.date API for EOL status
  * License databases for license type
  * Internal restricted package lists
* Record normalized dependency data in the Component JSON.

**When to use:** When you need to validate manifest-specific properties (lock file existence, version pinning, registry configuration) or when SBOM generation is not feasible.

### Approach B: SBOM-Based Analysis

Generate or consume a Software Bill of Materials (SBOM) and analyze its contents.

**How it works:**
* **Option 1 (auto-generate):** Use a code collector to automatically run an open-source SBOM generator (e.g., Syft, Trivy, cdxgen) to produce an SBOM in SPDX or CycloneDX format.
* **Option 2 (consume existing):** If the CI pipeline already generates an SBOM, collect it via a CI collector (see Strategy 1) and parse its contents.
* Extract dependency information, licenses, and package metadata from the SBOM.
* Cross-reference against external data sources for EOL status, restricted packages, etc.
* Record both the raw SBOM (under `.sbom.native`) and normalized data in the Component JSON.

**When to use:** When comprehensive dependency analysis is needed (including transitive dependencies), when license information is important, or when SBOM generation is already part of compliance requirements.

**Advantages of SBOM approach:**
* Captures transitive dependencies accurately
* Includes license information from package metadata
* Standard format enables tooling interoperability
* Satisfies SBOM-related compliance requirements simultaneously

### What policies can assert (both approaches):
* No EOL dependencies
* No restricted/forbidden libraries
* All licenses are approved
* Lock file exists and is committed (Approach A only)
* Dependencies use exact versions, not ranges (Approach A only)
* Dependencies come from approved registries
* SBOM was generated and is valid (Approach B only)

---

## Strategy 13: Container Registry Policies

React to container registry events to verify image metadata, signatures, and provenance.

**How it works:**
* Use a registry collector (coming soon) to react to container registries (Docker Hub, GCR, ECR, etc.) for image metadata.
* Check for:
  * Image signatures (cosign, Notary, Docker Content Trust)
  * Provenance attestations (SLSA)
  * Image labels
  * Base image information
  * Vulnerability scan results (if registry provides them)

**What policies can assert:**
* Images are signed with approved keys
* Provenance attestations exist and meet SLSA level requirements
* Required labels are present (Git SHA, build timestamp, source URL)
* Base images are current and approved

---

## Strategy 14: Historical Trend Analysis via Component JSON History

Analyze trends over time by querying historical Component JSONs rather than parsing Git history directly.

**Anti-pattern to avoid:** Do not parse Git history directly in a code collector to determine freshness or trends. Git history parsing is fragile and doesn't leverage Lunar's data model.

**Correct approach:** Use Strategy 3 (Cross-Component and Historical Data Queries) with a focus on time-based analysis:

**How it works:**
1. **Collect point-in-time data:** Ensure collectors record relevant data on every commit (e.g., file hashes, timestamps, metrics, signed commit status). This builds up a historical record in Lunar's database.
2. **Query historical Component JSONs:** Use the Lunar SQL API in policies to query Component JSONs from previous commits or time periods.
3. **Analyze trends:** Compare current values against historical baselines or compute aggregates over time windows.

**What policies can assert:**
* README content hash has changed within the last X days (freshness)
* Documentation files have been modified recently (staleness detection)
* Metrics haven't regressed compared to N commits ago
* Required files existed continuously over a time period
* Activity level (commit frequency) meets minimum thresholds

**Key difference from direct Git parsing:**
* Git parsing: Collector runs `git log` and parses output → fragile, slow, inconsistent
* Lunar approach: Collectors record data per-commit → SQL API queries historical records → reliable, fast, leverages existing data

---

## Strategy 15: Runtime and Deployed State Verification

Verify the actual deployed/running state of services rather than just configuration.

**How it works:**
* Use a cron collector to make requests to deployed services or query monitoring systems.
* Verify:
  * Health endpoints return expected structure
  * Metrics endpoints expose required metrics
  * Deployed version matches expected version
  * Services are actually running and responsive

**What policies can assert:**
* Health check endpoint includes required fields
* Golden signal metrics are being emitted
* Deployed version is not too far behind source
* Service is responsive and healthy

**Note:** This strategy requires network access to production/staging environments and should be used carefully with appropriate security controls.

---

## Strategy 16: AST-Based Code Pattern Extraction

Use [ast-grep](https://ast-grep.github.io/) to extract specific code patterns based on syntax/AST rather than text matching.

**How it works:**
* Use a code collector to run `ast-grep` (sg) with YAML rule files defining patterns.
* Patterns use metavariables (`$VAR`, `$FUNC`, `$$$ARGS`) to match and capture code structure.
* Parse the JSON output and record findings in the Component JSON.

**Why ast-grep over regex?** Syntax-aware matching won't match inside strings/comments, works across 20+ languages, and captures matched sub-expressions.

**Example use cases:**
* Structured logging enforcement (detect `fmt.Printf` instead of `slog`)
* Prometheus metrics extraction (collect declared counters/gauges/histograms)
* Feature flag inventory (find LaunchDarkly/Unleash flag usages)
* Security anti-patterns (SQL string concatenation, `eval()`, hardcoded secrets)
* Deprecated API detection (track migration progress)
* Error handling verification (unhandled errors in Go, missing `await` in JS)

**What policies can assert:**
* No printf-style logging violations
* All Prometheus metrics follow naming conventions
* No usage of deprecated APIs
* No security anti-patterns (SQL injection risks, dangerous exec calls)
* Feature flags are documented and follow conventions
