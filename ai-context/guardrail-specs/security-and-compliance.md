# Security and Compliance Guardrails

This document specifies possible policies for the **Security and Compliance** category. These guardrails cover vulnerability scanning (SAST, SCA, containers, secrets), Software Bill of Materials (SBOM), secrets management, supply chain security, access controls, encryption requirements, and compliance framework adherence (SOC 2, NIST/SSDF, PCI-DSS, ISO 27001).

---

## Static Application Security Testing (SAST)

### Scan Execution

* `sec-sast-executed` **SAST scan is executed**: Static analysis security scanning must run as part of the CI/CD pipeline to detect security vulnerabilities in source code.
  * Collector(s): Detect SAST tool execution in CI pipeline (e.g., Semgrep, SonarQube, CodeQL, Checkmarx) and collect scan results
  * Component JSON:
    * `.sast` - Object containing SAST scan results (presence indicates scan ran)
    * `.sast.source.tool` - Name of the SAST tool used
    * `.sast.source.integration` - How the scan was triggered (e.g., "ci", "github_app")
  * Policy: Assert that SAST scan data exists
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sast-approved-tool` **SAST scan uses approved tool**: Organization must use a specific approved SAST tool for compliance requirements.
  * Collector(s): Detect which SAST tool was used and record tool name and version
  * Component JSON:
    * `.sast.source.tool` - Name of the SAST tool used
    * `.sast.source.version` - Version of the tool
  * Policy: Assert that the SAST tool matches an approved list
  * Configuration: List of approved SAST tools (e.g., ["semgrep", "sonarqube", "codeql"])
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

### Finding Thresholds

* `sec-no-critical-sast-findings` **No critical SAST findings**: Source code must have zero critical-severity security findings from static analysis.
  * Collector(s): Parse SAST scan results and categorize findings by severity
  * Component JSON:
    * `.sast.findings.critical` - Count of critical-severity findings
    * `.sast.summary.has_critical` - Boolean indicating presence of critical findings
  * Policy: Assert that critical finding count is zero
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-no-high-sast-findings` **No high-severity SAST findings**: Source code should not have high-severity security findings that could lead to exploits.
  * Collector(s): Parse SAST scan results and count high-severity findings
  * Component JSON:
    * `.sast.findings.high` - Count of high-severity findings
    * `.sast.summary.has_high` - Boolean indicating presence of high findings
  * Policy: Assert that high-severity finding count is zero or below threshold
  * Configuration: Maximum allowed high-severity findings (default: 0)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sast-findings-threshold` **SAST findings within acceptable threshold**: Total SAST findings across all severities must not exceed organizational limits.
  * Collector(s): Aggregate all SAST findings by severity level
  * Component JSON:
    * `.sast.findings.total` - Total count of all findings
    * `.sast.findings.critical` - Critical count
    * `.sast.findings.high` - High count
    * `.sast.findings.medium` - Medium count
    * `.sast.findings.low` - Low count
  * Policy: Assert that total findings or weighted score is within threshold
  * Configuration: Maximum total findings, or weighted scoring formula
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sast-no-new-findings-pr` **New SAST findings not introduced in PR**: Pull requests must not introduce new security findings compared to the base branch.
  * Collector(s): Compare SAST scan results between PR and base branch to identify delta
  * Component JSON:
    * `.sast.pr_delta.new_findings` - Count of new findings introduced in PR
    * `.sast.pr_delta.new_issues` - Array of new issues with details
  * Policy: Assert that no new findings are introduced
  * Configuration: Severity levels to check (e.g., critical and high only)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

### SLA Compliance

* `sec-sast-critical-sla` **Critical SAST findings addressed within SLA**: Critical security findings must be remediated within the defined SLA period.
  * Collector(s): Track finding age from first detection date and compare against current time
  * Component JSON:
    * `.sast.issues[]` - Array of individual findings with metadata
    * `.sast.issues[].first_detected` - ISO 8601 timestamp of first detection
    * `.sast.issues[].severity` - Severity level
    * `.sast.issues[].age_days` - Days since first detection
    * `.sast.sla.critical_overdue` - Count of critical findings past SLA
  * Policy: Assert that no critical findings exceed SLA age
  * Configuration: SLA period in days for critical findings (default: 7)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sast-high-sla` **High-severity SAST findings addressed within SLA**: High-severity findings must be remediated within the defined SLA period.
  * Collector(s): Track finding age for high-severity issues
  * Component JSON:
    * `.sast.issues[].age_days` - Days since first detection
    * `.sast.sla.high_overdue` - Count of high findings past SLA
  * Policy: Assert that no high-severity findings exceed SLA age
  * Configuration: SLA period in days for high-severity findings (default: 30)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

---

## Software Composition Analysis (SCA)

### Scan Execution

* `sec-sca-executed` **SCA scan is executed**: Dependency vulnerability scanning must run to identify known vulnerabilities in third-party packages.
  * Collector(s): Detect SCA tool execution in CI or via GitHub App integration (e.g., Snyk, Dependabot, Grype, OWASP Dependency-Check) and collect results
  * Component JSON:
    * `.sca` - Object containing SCA scan results (presence indicates scan ran)
    * `.sca.source.tool` - Name of the SCA tool used
    * `.sca.source.integration` - How the scan was triggered
  * Policy: Assert that SCA scan data exists
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sca-approved-tool` **SCA scan uses approved tool**: Organization must use a specific approved SCA tool for compliance requirements.
  * Collector(s): Detect which SCA tool was used and record tool name
  * Component JSON:
    * `.sca.source.tool` - Name of the SCA tool used
    * `.sca.source.version` - Version of the tool
  * Policy: Assert that the SCA tool matches an approved list
  * Configuration: List of approved SCA tools (e.g., ["snyk", "dependabot", "grype"])
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

### Vulnerability Thresholds

* `sec-no-critical-sca-vulns` **No critical SCA vulnerabilities**: Dependencies must have zero critical-severity known vulnerabilities.
  * Collector(s): Parse SCA scan results and categorize vulnerabilities by severity
  * Component JSON:
    * `.sca.vulnerabilities.critical` - Count of critical vulnerabilities
    * `.sca.summary.has_critical` - Boolean indicating presence of critical vulnerabilities
  * Policy: Assert that critical vulnerability count is zero
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-no-high-sca-vulns` **No high-severity SCA vulnerabilities**: Dependencies should not have high-severity known vulnerabilities.
  * Collector(s): Parse SCA scan results and count high-severity vulnerabilities
  * Component JSON:
    * `.sca.vulnerabilities.high` - Count of high-severity vulnerabilities
    * `.sca.summary.has_high` - Boolean indicating presence of high vulnerabilities
  * Policy: Assert that high-severity vulnerability count is zero or below threshold
  * Configuration: Maximum allowed high-severity vulnerabilities (default: 0)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sca-vulns-threshold` **SCA vulnerabilities within acceptable threshold**: Total vulnerability count must not exceed organizational limits.
  * Collector(s): Aggregate all vulnerabilities by severity
  * Component JSON:
    * `.sca.vulnerabilities.total` - Total vulnerability count
    * `.sca.vulnerabilities.critical` - Critical count
    * `.sca.vulnerabilities.high` - High count
    * `.sca.vulnerabilities.medium` - Medium count
    * `.sca.vulnerabilities.low` - Low count
  * Policy: Assert that total or weighted score is within threshold
  * Configuration: Maximum totals per severity or weighted scoring
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sca-vulns-fixable` **All SCA vulnerabilities have available fixes**: Detected vulnerabilities should have remediation paths available.
  * Collector(s): Parse SCA results for fix availability information
  * Component JSON:
    * `.sca.summary.all_fixable` - Boolean indicating all vulnerabilities are fixable
    * `.sca.findings[].fixable` - Boolean per finding
    * `.sca.findings[].fix_version` - Recommended fix version if available
  * Policy: Assert that all or a threshold of vulnerabilities have fixes available
  * Configuration: Minimum fixable percentage (default: 100%)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

### SLA Compliance

* `sec-sca-critical-sla` **Critical SCA vulnerabilities addressed within SLA**: Critical vulnerabilities must be remediated within the defined SLA period.
  * Collector(s): Track vulnerability age from first detection or CVE publication date
  * Component JSON:
    * `.sca.findings[].first_detected` - When vulnerability was first detected
    * `.sca.findings[].cve_published` - CVE publication date
    * `.sca.findings[].age_days` - Days since first detection
    * `.sca.sla.critical_overdue` - Count of critical vulnerabilities past SLA
  * Policy: Assert that no critical vulnerabilities exceed SLA age
  * Configuration: SLA period in days for critical vulnerabilities (default: 7)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-sca-high-sla` **High-severity SCA vulnerabilities addressed within SLA**: High-severity vulnerabilities must be remediated within the defined SLA period.
  * Collector(s): Track vulnerability age for high-severity issues
  * Component JSON:
    * `.sca.findings[].age_days` - Days since first detection
    * `.sca.sla.high_overdue` - Count of high vulnerabilities past SLA
  * Policy: Assert that no high-severity vulnerabilities exceed SLA age
  * Configuration: SLA period in days for high-severity vulnerabilities (default: 30)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

### Dependency Restrictions

* `sec-no-restricted-libraries` **No restricted libraries in use**: Dependencies must not include packages on the organization's restricted list.
  * Collector(s): Parse dependency manifests or SBOM and compare against restricted package list
  * Component JSON:
    * `.dependencies.packages[]` - Array of all dependencies
    * `.dependencies.restricted_packages` - Array of restricted packages found
    * `.dependencies.has_restricted` - Boolean indicating restricted packages present
  * Policy: Assert that no restricted packages are in use
  * Configuration: List of restricted package names or patterns
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

* `sec-no-eol-dependencies` **No end-of-life dependencies**: Dependencies must not be past their end-of-life date.
  * Collector(s): Cross-reference dependencies against endoflife.date API or internal EOL database
  * Component JSON:
    * `.dependencies.eol_packages[]` - Array of packages past EOL
    * `.dependencies.eol_packages[].name` - Package name
    * `.dependencies.eol_packages[].eol_date` - EOL date
    * `.dependencies.has_eol` - Boolean indicating EOL packages present
  * Policy: Assert that no EOL dependencies are in use
  * Configuration: Grace period after EOL (default: 0 days)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 2 (GitHub App Status Check Integration) or Strategy 5 (Auto-Running Scanners)

---

## Container Image Scanning

### Scan Execution

* `sec-container-scan-executed` **Container image scan is executed**: Built container images must be scanned for known vulnerabilities before deployment.
  * Collector(s): Detect container scanning tool execution in CI (e.g., Trivy, Grype, Clair, Aqua) and collect results
  * Component JSON:
    * `.container_scan` - Object containing scan results (presence indicates scan ran)
    * `.container_scan.source.tool` - Name of the scanning tool
    * `.container_scan.image` - Image reference that was scanned
  * Policy: Assert that container scan data exists for components that build images
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

* `sec-container-scan-approved-tool` **Container scan uses approved tool**: Organization must use a specific approved container scanning tool.
  * Collector(s): Detect which scanning tool was used
  * Component JSON:
    * `.container_scan.source.tool` - Name of the scanning tool
    * `.container_scan.source.version` - Version of the tool
  * Policy: Assert that the scanning tool matches an approved list
  * Configuration: List of approved container scanning tools
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

### Vulnerability Thresholds

* `sec-no-critical-container-vulns` **No critical container vulnerabilities**: Container images must have zero critical-severity vulnerabilities.
  * Collector(s): Parse container scan results and categorize by severity
  * Component JSON:
    * `.container_scan.vulnerabilities.critical` - Count of critical vulnerabilities
    * `.container_scan.summary.has_critical` - Boolean indicating critical vulnerabilities present
  * Policy: Assert that critical vulnerability count is zero
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

* `sec-no-high-container-vulns` **No high-severity container vulnerabilities**: Container images should not have high-severity vulnerabilities.
  * Collector(s): Parse container scan results for high-severity issues
  * Component JSON:
    * `.container_scan.vulnerabilities.high` - Count of high-severity vulnerabilities
    * `.container_scan.summary.has_high` - Boolean indicating high vulnerabilities present
  * Policy: Assert that high-severity count is zero or below threshold
  * Configuration: Maximum allowed high-severity vulnerabilities (default: 0)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

* `sec-container-base-image-current` **Container base image is current**: Base images should be recently updated and not stale.
  * Collector(s): Check base image age or version against latest available
  * Component JSON:
    * `.container_scan.os.family` - OS family (e.g., alpine, debian)
    * `.container_scan.os.version` - OS version
    * `.containers.definitions[].base_images[].version_current` - Boolean if version is latest
    * `.containers.definitions[].base_images[].days_since_release` - Age of base image version
  * Policy: Assert that base image is current or within acceptable age
  * Configuration: Maximum base image age in days (default: 90)
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

---

## Secret Scanning

### Scan Execution

* `sec-secret-scan-executed` **Secret scan is executed**: Code must be scanned for hardcoded secrets and credentials before merge.
  * Collector(s): Detect secret scanning tool execution in CI or pre-commit (e.g., Gitleaks, TruffleHog, detect-secrets) and collect results
  * Component JSON:
    * `.secrets` - Object containing secret scan results (presence indicates scan ran)
    * `.secrets.source.tool` - Name of the secret scanning tool
    * `.secrets.source.integration` - How the scan was triggered (e.g., "ci", "pre-commit")
  * Policy: Assert that secret scan data exists
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

* `sec-secret-scan-approved-tool` **Secret scan uses approved tool**: Organization must use a specific approved secret scanning tool.
  * Collector(s): Detect which secret scanning tool was used
  * Component JSON:
    * `.secrets.source.tool` - Name of the scanning tool
  * Policy: Assert that the scanning tool matches an approved list
  * Configuration: List of approved secret scanning tools
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

### Finding Requirements

* `sec-no-secrets-in-code` **No secrets detected in code**: No hardcoded secrets, API keys, or credentials should be present in the codebase.
  * Collector(s): Parse secret scan results for any detections
  * Component JSON:
    * `.secrets.findings.total` - Count of secrets detected
    * `.secrets.clean` - Boolean indicating no secrets found
    * `.secrets.issues[]` - Array of detected secrets with file locations
  * Policy: Assert that no secrets are detected
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

* `sec-no-secrets-in-history` **No secrets in commit history**: Git history must not contain previously committed secrets.
  * Collector(s): Run secret scanner against full git history, not just current state
  * Component JSON:
    * `.secrets.history_scan.performed` - Boolean indicating history was scanned
    * `.secrets.history_scan.findings` - Count of secrets in history
    * `.secrets.history_scan.clean` - Boolean indicating no historical secrets
  * Policy: Assert that no secrets exist in commit history
  * Configuration: Whether to enforce history scanning
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

* `sec-no-secrets-in-containers` **No secrets in container images**: Built container images must not contain embedded secrets.
  * Collector(s): Run secret scanner against container image layers after build
  * Component JSON:
    * `.secrets.container_scan.performed` - Boolean indicating container was scanned
    * `.secrets.container_scan.findings` - Count of secrets in image
    * `.secrets.container_scan.clean` - Boolean indicating no secrets in image
  * Policy: Assert that no secrets are embedded in container images
  * Configuration: Whether to enforce container secret scanning
  * Strategy: Strategy 1 (CI Tool Execution Detection) or Strategy 5 (Auto-Running Scanners)

---

## Software Bill of Materials (SBOM)

### Generation Requirements

* `sec-sbom-generated` **SBOM is generated**: A Software Bill of Materials must be generated as part of the CI/CD pipeline.
  * Collector(s): Detect SBOM generation tool execution (e.g., Syft, SPDX tools, CycloneDX tools) and verify output
  * Component JSON:
    * `.sbom.exists` - Boolean indicating SBOM was generated
    * `.sbom.source.tool` - Tool used to generate SBOM
    * `.sbom.source.integration` - How SBOM was generated (e.g., "ci")
    * `.ci.artifacts.sbom_generated` - CI step confirmation
  * Policy: Assert that SBOM was generated
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `sec-sbom-standard-format` **SBOM follows standard format**: SBOM must use an industry-standard format (SPDX or CycloneDX).
  * Collector(s): Parse SBOM file and validate format compliance
  * Component JSON:
    * `.sbom.format` - Format type (e.g., "spdx", "cyclonedx")
    * `.sbom.format_version` - Format specification version
    * `.sbom.valid` - Boolean indicating format is valid
  * Policy: Assert that SBOM uses an approved standard format
  * Configuration: List of approved formats (default: ["spdx", "cyclonedx"])
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `sec-sbom-required-fields` **SBOM includes required fields**: SBOM must contain all fields required by compliance frameworks.
  * Collector(s): Parse SBOM and validate presence of required fields
  * Component JSON:
    * `.sbom.has_supplier_info` - Boolean for supplier information
    * `.sbom.has_license_info` - Boolean for license information
    * `.sbom.has_version_info` - Boolean for version information
    * `.sbom.completeness_score` - Percentage of required fields present
  * Policy: Assert that all required fields are present
  * Configuration: List of required fields per compliance regime
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Publishing and Storage

* `sec-sbom-published` **SBOM is published to approved location**: Generated SBOM must be stored in an organization-approved artifact repository.
  * Collector(s): Verify SBOM was uploaded to approved storage (artifact registry, S3 bucket, etc.)
  * Component JSON:
    * `.sbom.published` - Boolean indicating SBOM was published
    * `.sbom.location` - URL or path where SBOM is stored
    * `.sbom.location_approved` - Boolean indicating location is on approved list
  * Policy: Assert that SBOM is published to approved location
  * Configuration: List of approved SBOM storage locations
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `sec-sbom-signed` **SBOM is signed**: SBOM must be cryptographically signed for integrity verification.
  * Collector(s): Check for signature file or embedded signature in SBOM
  * Component JSON:
    * `.sbom.signed` - Boolean indicating SBOM is signed
    * `.sbom.signature.method` - Signing method used (e.g., "cosign", "gpg")
    * `.sbom.signature.verified` - Boolean indicating signature is valid
  * Policy: Assert that SBOM has a valid signature
  * Configuration: Approved signing methods
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `sec-sbom-current` **SBOM is kept current with releases**: SBOM must be regenerated and published with each release.
  * Collector(s): Compare SBOM generation timestamp with latest release timestamp
  * Component JSON:
    * `.sbom.generated_at` - Timestamp of SBOM generation
    * `.sbom.release_version` - Version/tag associated with SBOM
    * `.sbom.matches_latest_release` - Boolean indicating SBOM is for current release
  * Policy: Assert that SBOM corresponds to latest release
  * Configuration: Maximum age of SBOM relative to release
  * Strategy: Strategy 1 (CI Tool Execution Detection)

---

## Secrets Management

### Vault Integration

* `sec-secrets-approved-vault` **Secrets reference approved vault**: Application configuration must retrieve secrets from approved vault systems (e.g., HashiCorp Vault, AWS Secrets Manager).
  * Collector(s): Parse application configuration, Kubernetes manifests, and IaC files for secret references
  * Component JSON:
    * `.secrets.vault_usage.detected` - Boolean indicating vault references found
    * `.secrets.vault_usage.providers` - Array of vault providers referenced
    * `.secrets.vault_usage.approved` - Boolean indicating all providers are approved
  * Policy: Assert that secrets are sourced from approved vault systems
  * Configuration: List of approved vault providers
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-no-plaintext-secrets-config` **No plaintext secrets in configuration files**: Configuration files must not contain plaintext passwords, API keys, or tokens.
  * Collector(s): Scan configuration files (yaml, json, env, properties) for secret patterns
  * Component JSON:
    * `.secrets.config_scan.performed` - Boolean indicating config files were scanned
    * `.secrets.config_scan.findings` - Count of plaintext secrets in config
    * `.secrets.config_scan.clean` - Boolean indicating no plaintext secrets
  * Policy: Assert that no plaintext secrets exist in configuration
  * Configuration: File patterns to scan
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-env-secrets-approved-sources` **Environment variables for secrets use approved sources**: Environment variables containing secrets must be injected from approved secret stores.
  * Collector(s): Parse Kubernetes manifests and deployment configs for env var secret sources
  * Component JSON:
    * `.k8s.workloads[].containers[].env_secrets.sources` - Array of secret sources for env vars
    * `.k8s.workloads[].containers[].env_secrets.all_approved` - Boolean for approved sources
  * Policy: Assert that all secret env vars use approved sources
  * Configuration: Approved secret source types (e.g., "secretRef", "external-secrets")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Secret Rotation

* `sec-secret-rotation-configured` **Secret rotation is configured**: Secrets must have rotation policies configured in the vault system.
  * Collector(s): Query vault system APIs (via cron collector) for rotation configuration
  * Component JSON:
    * `.secrets.rotation.configured` - Boolean indicating rotation is set up
    * `.secrets.rotation.secrets_without_rotation` - Array of secrets without rotation
    * `.secrets.rotation.all_have_rotation` - Boolean indicating all secrets have rotation
  * Policy: Assert that rotation is configured for all secrets
  * Configuration: Whether to require rotation for all secret types
  * Strategy: Strategy 10 (External Vendor API Integration)

* `sec-secrets-within-age` **Secrets have not exceeded maximum age**: Secrets must be rotated within the defined maximum lifetime.
  * Collector(s): Query vault system for secret creation/rotation timestamps
  * Component JSON:
    * `.secrets.rotation.oldest_secret_age_days` - Age of oldest secret in days
    * `.secrets.rotation.expired_secrets` - Array of secrets past maximum age
    * `.secrets.rotation.all_within_age` - Boolean indicating all secrets are current
  * Policy: Assert that no secrets exceed maximum age
  * Configuration: Maximum secret age in days (default: 90)
  * Strategy: Strategy 10 (External Vendor API Integration)

---

## Supply Chain Security

### Container Image Signing

* `sec-container-images-signed` **Container images are signed**: All published container images must be cryptographically signed.
  * Collector(s): Check container registry for image signatures (e.g., cosign, Notary, Docker Content Trust)
  * Component JSON:
    * `.containers.builds[].signed` - Boolean indicating image is signed
    * `.containers.builds[].signature.method` - Signing method used
    * `.containers.builds[].signature.verified` - Boolean indicating signature is valid
    * `.containers.summary.all_signed` - Boolean indicating all images are signed
  * Policy: Assert that all published images are signed
  * Configuration: Approved signing methods
  * Strategy: Strategy 13 (Container Registry Policies)

* `sec-container-signatures-verified` **Container image signatures are verified before deployment**: Deployment pipelines must verify image signatures before allowing deployment.
  * Collector(s): Detect signature verification step in CD pipeline or admission controller configuration
  * Component JSON:
    * `.ci.steps_executed.signature_verification` - Boolean indicating verification ran
    * `.containers.builds[].signature.verification_enforced` - Boolean for enforcement
  * Policy: Assert that signature verification is performed
  * Configuration: None
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Build Provenance

* `sec-build-provenance-attested` **Build provenance is attested**: Builds must generate provenance attestations (e.g., SLSA provenance) documenting build inputs and process.
  * Collector(s): Detect provenance generation in CI and validate attestation format
  * Component JSON:
    * `.containers.builds[].provenance.exists` - Boolean indicating provenance exists
    * `.containers.builds[].provenance.format` - Provenance format (e.g., "slsa", "in-toto")
    * `.containers.builds[].provenance.level` - SLSA level achieved
  * Policy: Assert that build provenance is generated
  * Configuration: Minimum SLSA level required (default: 1)
  * Strategy: Strategy 1 (CI Tool Execution Detection)

* `sec-build-provenance-published` **Build provenance is published**: Provenance attestations must be published alongside artifacts.
  * Collector(s): Verify provenance is attached to container images or published to transparency log
  * Component JSON:
    * `.containers.builds[].provenance.published` - Boolean indicating provenance is published
    * `.containers.builds[].provenance.location` - Where provenance is stored
  * Policy: Assert that provenance is published with artifacts
  * Configuration: Required publication locations
  * Strategy: Strategy 1 (CI Tool Execution Detection)

### Dependency Integrity

* `sec-deps-use-lockfiles` **Dependencies use lock files**: Package managers must use lock files to ensure reproducible builds.
  * Collector(s): Scan repository for presence of lock files appropriate to detected package managers
  * Component JSON:
    * `.dependencies.lock_files` - Array of lock files found
    * `.dependencies.package_managers` - Array of package managers detected
    * `.dependencies.all_have_lock_files` - Boolean indicating all package managers have lock files
  * Policy: Assert that lock files exist for all detected package managers
  * Configuration: None
  * Strategy: Strategy 12 (Dependency Manifest Analysis)

* `sec-deps-pinned` **Dependencies are pinned to specific versions**: Dependencies must not use floating versions or ranges.
  * Collector(s): Parse dependency manifests and check for version pinning
  * Component JSON:
    * `.dependencies.unpinned_packages` - Array of packages with floating versions
    * `.dependencies.all_pinned` - Boolean indicating all dependencies are pinned
  * Policy: Assert that all dependencies are pinned to specific versions
  * Configuration: Whether to allow minor/patch version ranges
  * Strategy: Strategy 12 (Dependency Manifest Analysis)

* `sec-deps-approved-registries` **Dependencies come from approved registries only**: Packages must only be pulled from organization-approved registries.
  * Collector(s): Parse dependency manifests and package manager configs for registry URLs
  * Component JSON:
    * `.dependencies.registries_used` - Array of registry URLs referenced
    * `.dependencies.unapproved_registries` - Array of registries not on approved list
    * `.dependencies.all_approved_registries` - Boolean indicating all registries approved
  * Policy: Assert that only approved registries are used
  * Configuration: List of approved registry URLs per ecosystem
  * Strategy: Strategy 12 (Dependency Manifest Analysis)

* `sec-artifact-signatures-verified` **Artifact signatures are verified during build**: Build processes must verify signatures of downloaded dependencies.
  * Collector(s): Detect signature verification configuration in build tools (e.g., Maven, npm, pip)
  * Component JSON:
    * `.dependencies.signature_verification.enabled` - Boolean indicating verification is configured
    * `.dependencies.signature_verification.tool` - Tool performing verification
  * Policy: Assert that dependency signature verification is enabled
  * Configuration: Whether to require for all ecosystems or specific ones
  * Strategy: Strategy 1 (CI Tool Execution Detection)

---

## Access Controls and Version Control Security

### Branch Protection

* `vcs-branch-protection-enabled` **Branch protection is enabled on default branch**: The default branch must have branch protection rules enabled.
  * Collector(s): Query VCS provider API (GitHub, GitLab, Bitbucket) for branch protection settings
  * Component JSON:
    * `.vcs.branch_protection.enabled` - Boolean indicating protection is enabled
    * `.vcs.branch_protection.branch` - Protected branch name
  * Policy: Assert that branch protection is enabled
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-pr-min-approvals` **Pull requests require minimum approvals**: Merging to protected branches must require a minimum number of approvals.
  * Collector(s): Query VCS provider API for required approvals setting
  * Component JSON:
    * `.vcs.branch_protection.require_pr` - Boolean indicating PRs are required
    * `.vcs.branch_protection.required_approvals` - Number of required approvals
  * Policy: Assert that required approvals meet or exceed minimum
  * Configuration: Minimum required approvals (default: 1, recommended: 2)
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-codeowner-review-required` **Codeowner review is required**: PRs must be approved by designated code owners.
  * Collector(s): Query VCS provider API for codeowner review requirement
  * Component JSON:
    * `.vcs.branch_protection.require_codeowner_review` - Boolean indicating codeowner review required
  * Policy: Assert that codeowner review is required
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-status-checks-required` **Status checks are required before merge**: PRs must pass all required status checks before merging.
  * Collector(s): Query VCS provider API for required status checks configuration
  * Component JSON:
    * `.vcs.branch_protection.require_status_checks` - Boolean indicating status checks required
    * `.vcs.branch_protection.required_checks` - Array of required check names
  * Policy: Assert that status checks are required
  * Configuration: List of mandatory status checks
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-no-force-push` **Force pushes are disabled**: Force pushing to protected branches must be disabled.
  * Collector(s): Query VCS provider API for force push settings
  * Component JSON:
    * `.vcs.branch_protection.allow_force_push` - Boolean indicating if force push allowed
  * Policy: Assert that force push is disabled
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-branch-deletion-restricted` **Branch deletion is restricted**: Protected branches must not be deletable without special permissions.
  * Collector(s): Query VCS provider API for branch deletion settings
  * Component JSON:
    * `.vcs.branch_protection.allow_deletion` - Boolean indicating if deletion allowed
  * Policy: Assert that branch deletion is restricted
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

### Commit Security

* `vcs-signed-commits-required` **Signed commits are required**: All commits to protected branches must be cryptographically signed.
  * Collector(s): Query VCS provider API for commit signing requirements
  * Component JSON:
    * `.vcs.branch_protection.require_signed_commits` - Boolean indicating signed commits required
    * `.vcs.commit_signing.enforcement` - Enforcement level
  * Policy: Assert that commit signing is required
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-commits-reference-ticket` **Commits reference approved ticket/issue**: All commits or PRs must reference a valid ticket from the issue tracker.
  * Collector(s): Parse commit messages and PR titles for ticket references, validate against issue tracker API
  * Component JSON:
    * `.vcs.pr.ticket.id` - Extracted ticket ID
    * `.vcs.pr.ticket.valid` - Boolean indicating ticket exists in issue tracker
    * `.vcs.pr.ticket.source` - Issue tracker system (e.g., "jira", "github")
  * Policy: Assert that a valid ticket reference exists
  * Configuration: Ticket pattern regex, issue tracker integration
  * Strategy: Strategy 11 (VCS Provider API Queries)

---

## Encryption Requirements

### Data in Transit

* `sec-apis-require-tls` **APIs require TLS/HTTPS**: All service endpoints must enforce encrypted connections.
  * Collector(s): Parse API specs, Kubernetes Services, and Ingress configurations for TLS requirements
  * Component JSON:
    * `.api.all_secured` - Boolean indicating all endpoints use TLS
    * `.k8s.ingresses[].tls_enabled` - Boolean per Ingress
    * `.k8s.services[].tls_required` - Boolean per Service
  * Policy: Assert that TLS is required for all endpoints
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-tls-version-enforced` **Secure TLS versions are enforced**: Only TLS 1.2 or higher must be accepted.
  * Collector(s): Parse load balancer, ingress, and API gateway configurations for TLS version settings
  * Component JSON:
    * `.iac.resources[].ssl_policy` - SSL/TLS policy name or version
    * `.k8s.ingresses[].tls_min_version` - Minimum TLS version configured
    * `.containers.tls_config.min_version` - Application TLS configuration
  * Policy: Assert that minimum TLS version meets requirements
  * Configuration: Minimum TLS version (default: "1.2")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-cipher-suites-configured` **Secure cipher suites are configured**: Only approved cipher suites must be enabled.
  * Collector(s): Parse TLS configuration for cipher suite settings
  * Component JSON:
    * `.iac.resources[].cipher_suites` - Array of enabled cipher suites
    * `.containers.tls_config.cipher_suites` - Application cipher configuration
    * `.containers.tls_config.has_weak_ciphers` - Boolean indicating weak ciphers present
  * Policy: Assert that only approved cipher suites are enabled
  * Configuration: List of approved cipher suites, list of forbidden ciphers
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Data at Rest

* `sec-db-encryption-at-rest` **Databases have encryption at rest enabled**: All database resources must have encryption at rest configured.
  * Collector(s): Parse IaC files (Terraform, CloudFormation) for database encryption settings
  * Component JSON:
    * `.iac.resources[type="database"].encrypted` - Boolean per database resource
    * `.iac.datastores.all_encrypted` - Boolean indicating all datastores encrypted
  * Policy: Assert that all databases have encryption enabled
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-storage-encryption` **Storage buckets have encryption enabled**: Object storage (S3, GCS, Azure Blob) must have encryption configured.
  * Collector(s): Parse IaC files for storage bucket encryption settings
  * Component JSON:
    * `.iac.resources[type="storage"].encrypted` - Boolean per storage resource
    * `.iac.resources[type="storage"].encryption_type` - Type of encryption (SSE, KMS, etc.)
  * Policy: Assert that all storage has encryption enabled
  * Configuration: Required encryption type (e.g., KMS-managed keys)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-approved-key-management` **Encryption uses approved key management**: Encryption keys must be managed by approved KMS systems.
  * Collector(s): Parse encryption configurations for key source
  * Component JSON:
    * `.iac.resources[].encryption_key_source` - Where encryption key comes from
    * `.iac.resources[].kms_key_id` - KMS key identifier if used
    * `.iac.encryption.all_kms_managed` - Boolean indicating all keys are KMS-managed
  * Policy: Assert that encryption uses approved key management
  * Configuration: Required key management approach (e.g., "kms", "hsm")
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Compliance Framework Adherence

### SOC 2 Controls

* `comply-soc2-audit-logging` **SOC 2 audit logging is enabled**: Systems must maintain audit logs as required by SOC 2 Trust Service Criteria.
  * Collector(s): Verify audit logging configuration in IaC, application config, and cloud settings
  * Component JSON:
    * `.compliance.controls.audit_logging` - Boolean indicating audit logging enabled
    * `.observability.logging.audit_enabled` - Boolean for audit log configuration
  * Policy: Assert that audit logging is properly configured
  * Configuration: Required audit log retention period
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

* `comply-soc2-access-controls` **SOC 2 access controls are documented**: Access control policies must be documented and enforced.
  * Collector(s): Check for access control documentation in catalog annotations or repository files
  * Component JSON:
    * `.compliance.controls.access_controls` - Boolean indicating access controls documented
    * `.catalog.annotations.access_control_doc` - Link to access control documentation
  * Policy: Assert that access control documentation exists
  * Configuration: Required documentation location
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

* `comply-soc2-change-management` **SOC 2 change management process is followed**: All changes must follow the documented change management process.
  * Collector(s): Verify PR requirements, approvals, and CI/CD gates are in place
  * Component JSON:
    * `.compliance.controls.change_management` - Boolean indicating change management enforced
    * `.vcs.branch_protection.enabled` - Branch protection as part of change management
    * `.ci.steps_executed.approval_gate` - Boolean for deployment approval gate
  * Policy: Assert that change management controls are enforced
  * Configuration: Required change management controls
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

### PCI-DSS Requirements

* `comply-pci-data-handling` **PCI-DSS data handling is compliant**: Components handling cardholder data must meet PCI-DSS requirements.
  * Collector(s): Check component tags and data classification, verify PCI controls are in place
  * Component JSON:
    * `.compliance.regimes` - Array of applicable compliance regimes
    * `.compliance.data_classification.contains_pci` - Boolean indicating PCI data handling
    * `.compliance.pci.controls_implemented` - Array of implemented PCI controls
  * Policy: Assert that PCI-tagged components implement required controls
  * Configuration: List of required PCI controls per service tier
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

* `comply-pci-network-segmentation` **PCI-DSS network segmentation is verified**: Systems handling PCI data must be in segmented networks.
  * Collector(s): Parse IaC and Kubernetes network policies for segmentation
  * Component JSON:
    * `.iac.resources[].network_segmented` - Boolean indicating network isolation
    * `.k8s.network_policies[].applied` - Boolean indicating NetworkPolicy applied
    * `.compliance.pci.network_segmented` - Boolean for PCI network compliance
  * Policy: Assert that PCI components have network segmentation
  * Configuration: Required segmentation approach
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

### GDPR/Privacy Controls

* `comply-gdpr-data-classification` **GDPR data classification is documented**: Services must document what personal data they process.
  * Collector(s): Check catalog annotations and documentation for data classification
  * Component JSON:
    * `.compliance.data_classification.documented` - Boolean indicating classification exists
    * `.compliance.data_classification.contains_pii` - Boolean indicating PII processing
    * `.compliance.data_classification.pii_types` - Array of PII types handled
  * Policy: Assert that data classification is documented
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

* `comply-gdpr-data-retention` **GDPR data retention policies are defined**: Services handling personal data must have documented retention policies.
  * Collector(s): Check catalog annotations and documentation for retention policy
  * Component JSON:
    * `.compliance.gdpr.retention_policy_defined` - Boolean indicating policy exists
    * `.compliance.gdpr.retention_period_days` - Documented retention period
    * `.catalog.annotations.data_retention_policy` - Link to retention policy
  * Policy: Assert that retention policy is documented for PII-handling services
  * Configuration: Maximum retention period for different data types
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

* `comply-gdpr-region-compliance` **GDPR region compliance is documented**: Services must document which regions data is stored and processed.
  * Collector(s): Check catalog annotations and IaC for region configuration
  * Component JSON:
    * `.compliance.gdpr.regions_documented` - Boolean indicating region info documented
    * `.compliance.gdpr.processing_regions` - Array of regions where data is processed
    * `.iac.resources[].region` - Region per resource
  * Policy: Assert that data processing regions are documented
  * Configuration: List of approved regions
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

### HIPAA Requirements

* `comply-hipaa-controls` **HIPAA controls are implemented**: Services handling PHI must implement HIPAA-required controls.
  * Collector(s): Check component tags and verify HIPAA controls are in place
  * Component JSON:
    * `.compliance.regimes` - Array including "hipaa" if applicable
    * `.compliance.data_classification.contains_phi` - Boolean indicating PHI handling
    * `.compliance.hipaa.controls_implemented` - Array of implemented HIPAA controls
  * Policy: Assert that HIPAA-tagged components implement required controls
  * Configuration: List of required HIPAA controls
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

### NIST/SSDF Controls

* `comply-nist-ssdf` **NIST SSDF secure development practices are followed**: Development process must align with NIST Secure Software Development Framework.
  * Collector(s): Verify SSDF practices through collector checks (SBOM, security scanning, code review)
  * Component JSON:
    * `.compliance.ssdf.practices_implemented` - Array of implemented SSDF practices
    * `.compliance.ssdf.compliance_score` - Percentage of SSDF practices met
  * Policy: Assert that minimum SSDF practices are implemented
  * Configuration: List of required SSDF practices
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

### ISO 27001 Requirements

* `comply-iso27001-controls` **ISO 27001 controls are documented**: Services must document how they meet ISO 27001 control objectives.
  * Collector(s): Check for ISO 27001 control documentation in catalog or repository
  * Component JSON:
    * `.compliance.iso27001.controls_documented` - Boolean indicating documentation exists
    * `.compliance.iso27001.control_mapping` - Mapping of implemented controls
    * `.catalog.annotations.iso27001_controls` - Link to control documentation
  * Policy: Assert that ISO 27001 control documentation exists
  * Configuration: Required control documentation format
  * Strategy: Strategy 8 (File Parsing and Schema Extraction) or Strategy 10 (External Vendor API Integration)

---

## Data Classification and Handling

### Classification Requirements

* `sec-data-classification-assigned` **Data classification is assigned**: All services must have a data classification level assigned.
  * Collector(s): Check catalog annotations, repository metadata, or classification files for data classification
  * Component JSON:
    * `.compliance.data_classification.level` - Classification level (e.g., public, internal, confidential, restricted)
    * `.catalog.annotations.data_classification` - Classification from catalog
  * Policy: Assert that data classification is assigned
  * Configuration: Valid classification levels
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-pii-handling-documented` **PII handling is documented**: Services processing PII must document what PII they handle and how.
  * Collector(s): Check for PII documentation in catalog annotations or repository documentation
  * Component JSON:
    * `.compliance.data_classification.contains_pii` - Boolean indicating PII processing
    * `.compliance.data_classification.pii_documented` - Boolean indicating PII handling is documented
    * `.compliance.data_classification.pii_types` - Array of PII types
  * Policy: Assert that PII-handling services have documentation
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-sensitive-data-logging` **Sensitive data is logged appropriately**: PII and other sensitive data must not appear in logs without proper redaction.
  * Collector(s): Check logging configuration for PII redaction settings, or use SAST rules for log statement analysis
  * Component JSON:
    * `.observability.logging.pii_redaction_enabled` - Boolean indicating redaction is configured
    * `.sast.findings[category="logging-pii"]` - SAST findings related to PII in logs
  * Policy: Assert that PII redaction is enabled for services handling sensitive data
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Security Misconfiguration Prevention

### Debug and Development Settings

* `sec-no-debug-mode-prod` **Debug mode is disabled in production**: Applications must not run in debug mode in production environments.
  * Collector(s): Parse application configuration and environment variables for debug settings
  * Component JSON:
    * `.containers.definitions[].env_vars.DEBUG` - Debug environment variable if set
    * `.k8s.workloads[].containers[].env.DEBUG` - Debug setting in Kubernetes
    * `.security.misconfig.debug_enabled` - Boolean indicating debug mode detected
  * Policy: Assert that debug mode is not enabled for production components
  * Configuration: Environment variable patterns to check
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-no-error-details-exposed` **Error details are not exposed to users**: Applications must not return stack traces or internal error details to end users.
  * Collector(s): Check application configuration for error handling settings, or verify through SAST rules
  * Component JSON:
    * `.security.misconfig.verbose_errors` - Boolean indicating verbose errors enabled
    * `.sast.findings[category="error-exposure"]` - Findings related to error exposure
  * Policy: Assert that verbose error mode is disabled
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `sec-no-default-credentials` **Default credentials are not in use**: Applications and infrastructure must not use default credentials.
  * Collector(s): Scan configuration files and IaC for known default credential patterns
  * Component JSON:
    * `.security.misconfig.default_credentials` - Boolean indicating default creds detected
    * `.secrets.default_credential_findings` - Array of default credential instances found
  * Policy: Assert that no default credentials are detected
  * Configuration: Patterns for default credentials to detect
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Security Headers

* `sec-security-headers-configured` **Security headers are configured**: Web applications must set appropriate security headers (CSP, HSTS, X-Frame-Options, etc.).
  * Collector(s): Parse application configuration, reverse proxy configs, or verify through dynamic scanning
  * Component JSON:
    * `.security.headers.csp_enabled` - Boolean for Content-Security-Policy
    * `.security.headers.hsts_enabled` - Boolean for Strict-Transport-Security
    * `.security.headers.xframe_enabled` - Boolean for X-Frame-Options
    * `.security.headers.all_required_present` - Boolean indicating all required headers set
  * Policy: Assert that required security headers are configured
  * Configuration: List of required security headers
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Code-Level Security Patterns (AST-Based)

These guardrails use Strategy 16 (AST-Based Code Pattern Extraction) to detect security anti-patterns directly in source code via structural analysis.

### Injection Vulnerabilities

* `sec-no-sql-string-concat` **No SQL string concatenation**: Code must not construct SQL queries using string concatenation, which can lead to SQL injection vulnerabilities.
  * Collector(s): Use ast-grep to find patterns like `db.Query($SQL + $VAR)` or string interpolation in SQL contexts
  * Component JSON:
    * `.code_patterns.security.sql_concat.count` - Number of SQL concatenation patterns found
    * `.code_patterns.security.sql_concat.locations` - Array of file/line locations
    * `.code_patterns.security.sql_concat.clean` - Boolean indicating no patterns found
  * Policy: Assert that no SQL string concatenation patterns are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-command-injection` **No command injection patterns**: Code must not pass user input directly to shell commands or system calls.
  * Collector(s): Use ast-grep to detect patterns like `os.system($VAR)`, `subprocess.call($CMD, shell=True)`, `exec.Command($VAR)`
  * Component JSON:
    * `.code_patterns.security.command_injection.count` - Number of dangerous patterns found
    * `.code_patterns.security.command_injection.locations` - Array of file/line locations
    * `.code_patterns.security.command_injection.clean` - Boolean indicating no patterns found
  * Policy: Assert that no command injection patterns are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-path-traversal` **No path traversal patterns**: Code must not construct file paths using unsanitized user input.
  * Collector(s): Use ast-grep to detect patterns like `os.Open($BASE + $USER_INPUT)` or `path.Join($BASE, $USER_INPUT)` without validation
  * Component JSON:
    * `.code_patterns.security.path_traversal.count` - Number of patterns found
    * `.code_patterns.security.path_traversal.locations` - Array of file/line locations
  * Policy: Assert that no path traversal patterns are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Dangerous Functions

* `sec-no-eval-exec` **No eval or exec usage**: Code must not use eval(), exec(), or similar dynamic code execution functions.
  * Collector(s): Use ast-grep to detect `eval($$$)`, `exec($$$)`, `Function($$$)()` patterns
  * Component JSON:
    * `.code_patterns.security.eval_exec.count` - Number of eval/exec usages found
    * `.code_patterns.security.eval_exec.locations` - Array of file/line locations
    * `.code_patterns.security.eval_exec.clean` - Boolean indicating no patterns found
  * Policy: Assert that no eval/exec patterns are detected
  * Configuration: Allowed exceptions with justification
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-unsafe-deserialization` **No unsafe deserialization**: Code must not deserialize untrusted data using unsafe methods (pickle, yaml.load without SafeLoader, etc.).
  * Collector(s): Use ast-grep to detect `pickle.loads($$$)`, `yaml.load($$$)` without Loader, `Marshal.load($$$)`
  * Component JSON:
    * `.code_patterns.security.unsafe_deserialization.count` - Number of unsafe patterns found
    * `.code_patterns.security.unsafe_deserialization.locations` - Array of file/line locations
  * Policy: Assert that no unsafe deserialization patterns are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-unsafe-reflection` **No unsafe reflection**: Code must not use reflection to invoke methods based on user input.
  * Collector(s): Use ast-grep to detect patterns where user input flows into reflection APIs
  * Component JSON:
    * `.code_patterns.security.unsafe_reflection.count` - Number of patterns found
    * `.code_patterns.security.unsafe_reflection.locations` - Array of file/line locations
  * Policy: Assert that no unsafe reflection patterns are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Cryptography

* `sec-no-weak-crypto` **No weak cryptographic algorithms**: Code must not use deprecated/weak cryptographic algorithms (MD5, SHA1 for security, DES, RC4).
  * Collector(s): Use ast-grep to detect `md5.New()`, `sha1.New()`, `crypto.MD5`, `hashlib.md5()` in security contexts
  * Component JSON:
    * `.code_patterns.security.weak_crypto.count` - Number of weak crypto usages
    * `.code_patterns.security.weak_crypto.algorithms` - Array of weak algorithms found
    * `.code_patterns.security.weak_crypto.locations` - Array of file/line locations
  * Policy: Assert that no weak cryptographic algorithms are used for security purposes
  * Configuration: Allowed algorithms (exclude MD5/SHA1 used for checksums only)
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-hardcoded-crypto-keys` **No hardcoded cryptographic keys**: Code must not contain hardcoded encryption keys, IVs, or salts.
  * Collector(s): Use ast-grep to detect patterns like `key = "..."` or `iv = []byte{...}` in crypto contexts
  * Component JSON:
    * `.code_patterns.security.hardcoded_keys.count` - Number of hardcoded keys found
    * `.code_patterns.security.hardcoded_keys.locations` - Array of file/line locations
  * Policy: Assert that no hardcoded cryptographic material is detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-insecure-random` **No insecure random for security purposes**: Code must use cryptographically secure random number generators for security-sensitive operations.
  * Collector(s): Use ast-grep to detect `math/rand` or `random.random()` usage in security contexts (tokens, passwords, keys)
  * Component JSON:
    * `.code_patterns.security.insecure_random.count` - Number of insecure random usages
    * `.code_patterns.security.insecure_random.locations` - Array of file/line locations
  * Policy: Assert that cryptographic random is used for security operations
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Credential Patterns

* `sec-no-hardcoded-credentials` **No hardcoded credentials in code**: Code must not contain hardcoded passwords, API keys, or tokens.
  * Collector(s): Use ast-grep to detect patterns like `password = "..."`, `apiKey = "..."`, `token = "..."`
  * Component JSON:
    * `.code_patterns.security.hardcoded_credentials.count` - Number of hardcoded credentials
    * `.code_patterns.security.hardcoded_credentials.types` - Types of credentials found
    * `.code_patterns.security.hardcoded_credentials.locations` - Array of file/line locations
  * Policy: Assert that no hardcoded credentials are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-credentials-in-urls` **No credentials embedded in URLs**: Code must not embed credentials in URL strings.
  * Collector(s): Use ast-grep to detect URL patterns containing credentials like `http://user:pass@host`
  * Component JSON:
    * `.code_patterns.security.credential_urls.count` - Number of credential URLs found
    * `.code_patterns.security.credential_urls.locations` - Array of file/line locations
  * Policy: Assert that no credentials are embedded in URLs
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

### Logging and Information Disclosure

* `sec-no-sensitive-data-logging` **No sensitive data in log statements**: Log statements must not include passwords, tokens, PII, or other sensitive data.
  * Collector(s): Use ast-grep to detect logging calls that include sensitive variable names or patterns
  * Component JSON:
    * `.code_patterns.security.sensitive_logging.count` - Number of sensitive logging patterns
    * `.code_patterns.security.sensitive_logging.locations` - Array of file/line locations
  * Policy: Assert that no sensitive data logging patterns are detected
  * Configuration: Sensitive field patterns to detect
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)

* `sec-no-stack-trace-exposure` **No stack trace exposure to users**: Code must not return stack traces or internal errors directly to users.
  * Collector(s): Use ast-grep to detect patterns like returning `err.Error()` or `traceback` in HTTP responses
  * Component JSON:
    * `.code_patterns.security.stack_trace_exposure.count` - Number of exposure patterns
    * `.code_patterns.security.stack_trace_exposure.locations` - Array of file/line locations
  * Policy: Assert that no stack trace exposure patterns are detected
  * Configuration: None
  * Strategy: Strategy 16 (AST-Based Code Pattern Extraction)
