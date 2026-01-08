# Repository and Ownership Guardrails

This document specifies possible policies for the **Repository and Ownership** category. These guardrails cover documentation standards, code ownership validation, version control settings, service catalog integration, and repository configuration.

---

## Documentation Standards

### README Policies

* `docs-readme-exists` **README file exists**: Every repository must contain a README file at the root level to provide essential documentation for developers.
  * Collector(s): Scan the repository root for README.md or README files
  * Component JSON:
    * `.repo.readme.exists` - Boolean indicating if README file is present
    * `.repo.readme.path` - Path to the README file (e.g., "README.md")
  * Policy: Assert that `.repo.readme.exists` is true
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-min-length` **README has minimum length**: README must contain substantive content, not just a title or placeholder text.
  * Collector(s): Count the number of lines and/or words in the README file
  * Component JSON:
    * `.repo.readme.lines` - Number of lines in the README
    * `.repo.readme.words` - Number of words in the README
    * `.repo.readme.chars` - Number of characters in the README
  * Policy: Assert that line count, word count, or character count exceeds the configured threshold
  * Configuration: Minimum lines (default: 20), minimum words (default: 100)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-required-sections` **README contains required sections**: README must include organization-mandated sections such as Installation, Usage, Contributing, and License.
  * Collector(s): Parse the README for markdown headings (lines starting with #, ##, ###) and extract section titles
  * Component JSON:
    * `.repo.readme.sections` - Array of section heading strings found in the README
    * `.repo.readme.sections_lowercase` - Normalized lowercase version for case-insensitive matching
  * Policy: Assert that all required section names are present in the sections array (case-insensitive matching)
  * Configuration: List of required section names (e.g., ["Installation", "Usage", "API", "Contributing"])
  * Strategy: Strategy 7 (LLM-Assisted Analysis) or Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-description` **README contains description section**: README must have a clear description or overview section explaining what the service/library does.
  * Collector(s): Parse the README for description-related sections (Description, Overview, About, Introduction)
  * Component JSON:
    * `.repo.readme.has_description` - Boolean indicating presence of description section
    * `.repo.readme.description_section` - The name of the description section found
  * Policy: Assert that a description section exists
  * Configuration: Acceptable section names for description (default: ["Description", "Overview", "About", "Introduction"])
  * Strategy: Strategy 7 (LLM-Assisted Analysis) or Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-architecture` **README contains architecture section**: Critical services must document their architecture in the README for understanding system design.
  * Collector(s): Parse the README for architecture-related headings
  * Component JSON:
    * `.repo.readme.has_architecture` - Boolean indicating presence of architecture section
  * Policy: Assert that architecture section exists for components with specific tags
  * Configuration: Tags that require architecture documentation (e.g., ["tier1", "core-service"])
  * Strategy: Strategy 7 (LLM-Assisted Analysis) or Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-local-dev` **README contains local development instructions**: README must include instructions for running the service locally.
  * Collector(s): Parse the README for development-related sections (Local Development, Development, Getting Started, Running Locally)
  * Component JSON:
    * `.repo.readme.has_local_dev` - Boolean indicating presence of local development section
  * Policy: Assert that local development instructions exist
  * Configuration: Acceptable section names for local development documentation
  * Strategy: Strategy 7 (LLM-Assisted Analysis) or Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-api-docs` **README contains API documentation or link**: Services with APIs must document endpoints or link to API documentation.
  * Collector(s): Parse the README for API-related sections or URLs pointing to API docs
  * Component JSON:
    * `.repo.readme.has_api_section` - Boolean indicating presence of API section
    * `.repo.readme.api_doc_links` - Array of URLs to API documentation found in README
  * Policy: Assert that API documentation is present for components tagged as APIs
  * Configuration: Tags that require API documentation (e.g., ["api", "service"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-readme-recent-update` **README was updated recently**: README should be kept up-to-date, with modifications within a reasonable timeframe.
  * Collector(s): Query git history for the last modification date of the README file
  * Component JSON:
    * `.repo.readme.last_modified` - ISO 8601 timestamp of last README modification
    * `.repo.readme.days_since_update` - Number of days since last update
  * Policy: Assert that days since update is less than configured threshold
  * Configuration: Maximum days since update (default: 180)
  * Strategy: Strategy 14 (Historical Trend Analysis via Component JSON History)

### Runbook and Operational Documentation

* `docs-runbook-exists` **Runbook exists**: Production services must have a runbook documenting operational procedures.
  * Collector(s): Scan for runbook files in standard locations (docs/runbook.md, RUNBOOK.md, runbooks/) or links in catalog annotations
  * Component JSON:
    * `.oncall.runbook.exists` - Boolean indicating runbook presence
    * `.oncall.runbook.path` - File path to the runbook if in repository
    * `.oncall.runbook.url` - URL to external runbook if linked
  * Policy: Assert that runbook exists for production services
  * Configuration: Required for components with tags (e.g., ["production", "tier1", "tier2"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-runbook-location` **Runbook is in blessed location**: Runbook must be located in an organization-approved directory or documentation system.
  * Collector(s): Detect runbook file location and validate against allowed paths
  * Component JSON:
    * `.oncall.runbook.path` - File path to the runbook
    * `.oncall.runbook.in_blessed_location` - Boolean indicating if location is approved
  * Policy: Assert that runbook is in a blessed location
  * Configuration: List of blessed locations (e.g., ["docs/runbook.md", "runbooks/", "wiki/"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-runbook-required-sections` **Runbook contains required sections**: Runbook must include standard operational sections like Alerts, Troubleshooting, Escalation.
  * Collector(s): Parse runbook file for section headings
  * Component JSON:
    * `.oncall.runbook.sections` - Array of section headings in the runbook
  * Policy: Assert that required sections are present
  * Configuration: Required runbook sections (e.g., ["Alerts", "Troubleshooting", "Escalation", "Recovery Procedures"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-sla-slo-exists` **SLA/SLO documentation exists**: Services must document their service level objectives and agreements.
  * Collector(s): Scan for SLA/SLO sections in README, catalog annotations, or dedicated files
  * Component JSON:
    * `.oncall.sla.defined` - Boolean indicating SLA is documented
    * `.oncall.sla.location` - Where SLA is documented (file path or URL)
  * Policy: Assert that SLA documentation exists for applicable services
  * Configuration: Tags requiring SLA documentation (e.g., ["production", "customer-facing"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Required Links and References

* `docs-readme-valid-links` **Repository has valid links in README**: External links in README should be valid and not broken.
  * Collector(s): Extract all URLs from README and validate their accessibility (HTTP response check)
  * Component JSON:
    * `.repo.readme.links` - Array of all links found in README
    * `.repo.readme.broken_links` - Array of links that returned error status
    * `.repo.readme.links_valid` - Boolean indicating all links are valid
  * Policy: Assert that no broken links exist in README
  * Configuration: Timeout for link validation, exclusion patterns for internal URLs
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-observability-links` **Documentation links to observability dashboards**: README or catalog should link to monitoring dashboards.
  * Collector(s): Search README and catalog annotations for dashboard URLs (Grafana, Datadog, etc.)
  * Component JSON:
    * `.observability.dashboard.exists` - Boolean indicating dashboard link presence
    * `.observability.dashboard.url` - URL to the dashboard
    * `.catalog.annotations.grafana_dashboard` - Dashboard annotation from catalog
  * Policy: Assert that dashboard link exists for production services
  * Configuration: Tags requiring dashboard links
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `docs-logging-tracing-links` **Documentation links to logging/tracing**: README or catalog should link to logging and tracing systems.
  * Collector(s): Search README and catalog annotations for logging/tracing URLs
  * Component JSON:
    * `.observability.logging.url` - URL to logging dashboard
    * `.observability.tracing.url` - URL to tracing dashboard
    * `.catalog.annotations.logging_url` - Logging annotation from catalog
  * Policy: Assert that observability links exist for production services
  * Configuration: Required observability links
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Code Ownership

### CODEOWNERS Policies

* `ownership-codeowners-exists` **CODEOWNERS file exists**: Repository must have a CODEOWNERS file defining code ownership.
  * Collector(s): Scan for CODEOWNERS file in standard locations (root, .github/, docs/)
  * Component JSON:
    * `.ownership.codeowners.exists` - Boolean indicating CODEOWNERS presence
    * `.ownership.codeowners.path` - Path to the CODEOWNERS file
  * Policy: Assert that CODEOWNERS file exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ownership-codeowners-valid` **CODEOWNERS file is valid syntax**: CODEOWNERS file must have valid syntax that GitHub/GitLab can parse.
  * Collector(s): Parse CODEOWNERS file and validate syntax (use codeowners-validator or similar)
  * Component JSON:
    * `.ownership.codeowners.valid` - Boolean indicating syntax validity
    * `.ownership.codeowners.errors` - Array of syntax errors found
  * Policy: Assert that CODEOWNERS is syntactically valid
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ownership-codeowners-catchall` **CODEOWNERS has default catch-all rule**: CODEOWNERS must have a default rule (*, **) covering all files.
  * Collector(s): Parse CODEOWNERS and detect presence of catch-all pattern
  * Component JSON:
    * `.ownership.codeowners.has_default_rule` - Boolean indicating default rule presence
    * `.ownership.codeowners.default_owners` - Owners assigned to the default rule
  * Policy: Assert that a default catch-all rule exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ownership-codeowners-valid-refs` **CODEOWNERS references valid teams/users**: All teams and users referenced in CODEOWNERS must exist in the organization.
  * Collector(s): Extract all owner references from CODEOWNERS and validate against GitHub/GitLab API
  * Component JSON:
    * `.ownership.codeowners.owners` - Array of all owners referenced
    * `.ownership.codeowners.invalid_owners` - Array of owners that don't exist
    * `.ownership.codeowners.owners_valid` - Boolean indicating all owners exist
  * Policy: Assert that all referenced owners are valid
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `ownership-codeowners-active` **CODEOWNERS owners are active employees**: Owners referenced in CODEOWNERS should be active employees (not departed).
  * Collector(s): Cross-reference CODEOWNERS owners with HRIS system or user directory
  * Component JSON:
    * `.ownership.codeowners.owners` - Array of all owners referenced
    * `.ownership.codeowners.inactive_owners` - Array of owners no longer active
    * `.ownership.codeowners.all_owners_active` - Boolean indicating all owners are active
  * Policy: Assert that no inactive owners are referenced
  * Configuration: HRIS integration endpoint, grace period for recently departed
  * Strategy: Strategy 10 (External Vendor API Integration)

* `ownership-codeowners-min-owners` **CODEOWNERS has minimum number of owners**: Each file pattern should have at least a minimum number of owners for redundancy.
  * Collector(s): Parse CODEOWNERS and count owners per pattern
  * Component JSON:
    * `.ownership.codeowners.rules` - Array of rules with pattern and owner count
    * `.ownership.codeowners.min_owners_per_rule` - Minimum owners found across all rules
  * Policy: Assert that each rule has at least the minimum required owners
  * Configuration: Minimum owners per rule (default: 2)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ownership-codeowners-team-owners` **CODEOWNERS includes team owners**: CODEOWNERS should reference teams rather than just individuals for better ownership continuity.
  * Collector(s): Parse CODEOWNERS and classify owners as teams vs individuals
  * Component JSON:
    * `.ownership.codeowners.team_owners` - Array of team owners
    * `.ownership.codeowners.individual_owners` - Array of individual owners
    * `.ownership.codeowners.has_team_owners` - Boolean indicating team ownership exists
  * Policy: Assert that at least one team owner is present
  * Configuration: Whether to require teams only or allow mix
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Maintainer and Owner Policies

* `ownership-maintainers-defined` **Repository has defined maintainers**: Component must have explicitly defined maintainers in catalog or configuration.
  * Collector(s): Extract maintainer information from catalog-info.yaml, lunar.yml, or similar
  * Component JSON:
    * `.ownership.maintainers` - Array of maintainer emails or usernames
    * `.ownership.has_maintainers` - Boolean indicating maintainers are defined
  * Policy: Assert that maintainers are defined
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ownership-maintainers-active` **Maintainers are active employees**: All defined maintainers should be active employees.
  * Collector(s): Cross-reference maintainers with HRIS system
  * Component JSON:
    * `.ownership.maintainers` - Array of maintainers
    * `.ownership.inactive_maintainers` - Array of inactive maintainers
    * `.ownership.all_maintainers_active` - Boolean indicating all are active
  * Policy: Assert that no inactive maintainers exist
  * Configuration: HRIS integration details
  * Strategy: Strategy 10 (External Vendor API Integration)

* `ownership-component-owner` **Component has defined owner**: Every component must have a designated owner (individual or team).
  * Collector(s): Extract owner from catalog-info.yaml or component configuration
  * Component JSON:
    * `.catalog.entity.owner` - Owner identifier from catalog
    * `.ownership.owner` - Resolved owner information
  * Policy: Assert that owner is defined
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `ownership-owner-matches-codeowners` **Owner matches CODEOWNERS**: The component owner in the catalog should align with CODEOWNERS entries.
  * Collector(s): Compare catalog owner with CODEOWNERS default rule owners
  * Component JSON:
    * `.catalog.entity.owner` - Catalog owner
    * `.ownership.codeowners.default_owners` - CODEOWNERS default owners
    * `.ownership.owner_matches_codeowners` - Boolean indicating alignment
  * Policy: Assert that catalog owner appears in CODEOWNERS
  * Configuration: Whether exact match or team membership match is required
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Version Control Settings

### Branch Protection Policies

* `vcs-branch-protection` **Default branch has protection enabled**: The main/master branch must have branch protection rules enabled.
  * Collector(s): Query VCS API for branch protection settings
  * Component JSON:
    * `.vcs.branch_protection.enabled` - Boolean indicating protection is active
    * `.vcs.branch_protection.branch` - Protected branch name
  * Policy: Assert that branch protection is enabled
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-pr-reviews-required` **Branch protection requires pull request reviews**: Changes must go through PR review before merging.
  * Collector(s): Query VCS API for PR requirements in branch protection
  * Component JSON:
    * `.vcs.branch_protection.require_pr` - Boolean indicating PRs are required
  * Policy: Assert that PR reviews are required
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-min-approvals` **Branch protection requires minimum approvals**: PRs must have a minimum number of approvals before merge.
  * Collector(s): Query VCS API for required approval count
  * Component JSON:
    * `.vcs.branch_protection.required_approvals` - Number of required approvals
  * Policy: Assert that required approvals meets or exceeds threshold
  * Configuration: Minimum approvals required (default: 1)
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-codeowner-approval` **Branch protection requires CODEOWNER approval**: PRs modifying owned files must be approved by CODEOWNERS.
  * Collector(s): Query VCS API for CODEOWNER review requirements
  * Component JSON:
    * `.vcs.branch_protection.require_codeowner_review` - Boolean for CODEOWNER requirement
  * Policy: Assert that CODEOWNER review is required
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-status-checks` **Branch protection requires status checks**: PRs must pass required CI checks before merge.
  * Collector(s): Query VCS API for required status checks
  * Component JSON:
    * `.vcs.branch_protection.require_status_checks` - Boolean for status check requirement
    * `.vcs.branch_protection.required_checks` - List of required check names
  * Policy: Assert that status checks are required
  * Configuration: List of mandatory check names
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-no-force-push` **Force push is disabled on protected branches**: Force pushing should be prohibited on main branches.
  * Collector(s): Query VCS API for force push settings
  * Component JSON:
    * `.vcs.branch_protection.allow_force_push` - Boolean indicating if force push allowed
  * Policy: Assert that force push is disabled
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-branch-deletion-restricted` **Branch deletion is restricted**: Protected branches should not be deletable.
  * Collector(s): Query VCS API for branch deletion settings
  * Component JSON:
    * `.vcs.branch_protection.allow_deletion` - Boolean indicating if deletion allowed
  * Policy: Assert that branch deletion is disabled
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-linear-history` **Require linear history**: Protected branches should require linear history (no merge commits or squash required).
  * Collector(s): Query VCS API for linear history requirements
  * Component JSON:
    * `.vcs.branch_protection.require_linear_history` - Boolean for linear history requirement
  * Policy: Assert that linear history is required
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-signed-commits` **Require signed commits**: Commits to protected branches must be cryptographically signed.
  * Collector(s): Query VCS API for commit signing requirements
  * Component JSON:
    * `.vcs.branch_protection.require_signed_commits` - Boolean for signing requirement
  * Policy: Assert that signed commits are required
  * Configuration: None
  * Strategy: Strategy 11 (VCS Provider API Queries)

### Pull Request Policies

* `vcs-pr-title-convention` **PR title follows convention**: PR titles must follow naming conventions (e.g., include ticket references).
  * Collector(s): Extract PR title from VCS webhook/API in PR context
  * Component JSON:
    * `.vcs.pr.title` - PR title string
    * `.vcs.pr.title_matches_convention` - Boolean indicating convention compliance
  * Policy: Assert that PR title matches the required pattern
  * Configuration: Regex pattern for valid PR titles (e.g., "^\[?[A-Z]+-\d+\]?.*")
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-pr-description` **PR description is not empty**: PRs must include a meaningful description.
  * Collector(s): Extract PR description from VCS API
  * Component JSON:
    * `.vcs.pr.description` - PR description text
    * `.vcs.pr.description_length` - Character count of description
  * Policy: Assert that description exceeds minimum length
  * Configuration: Minimum description length (default: 50 characters)
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-pr-ticket-reference` **PR references a ticket**: PRs must reference an issue tracking ticket (Jira, GitHub Issues, etc.).
  * Collector(s): Parse PR title and description for ticket patterns
  * Component JSON:
    * `.vcs.pr.ticket.id` - Extracted ticket ID
    * `.vcs.pr.ticket.source` - Ticket system (jira, github, etc.)
    * `.vcs.pr.ticket.url` - URL to the ticket
  * Policy: Assert that a ticket reference is present
  * Configuration: Ticket patterns to match (e.g., Jira project keys)
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-pr-labels` **PR has appropriate labels**: PRs should have required labels for categorization.
  * Collector(s): Extract PR labels from VCS API
  * Component JSON:
    * `.vcs.pr.labels` - Array of label names on the PR
  * Policy: Assert that at least one required label is present
  * Configuration: Required label categories or specific labels
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-pr-size-limit` **PR size is within limits**: PRs should not be excessively large (too many files or lines changed).
  * Collector(s): Extract PR statistics from VCS API
  * Component JSON:
    * `.vcs.pr.files_changed` - Number of files changed
    * `.vcs.pr.additions` - Lines added
    * `.vcs.pr.deletions` - Lines deleted
  * Policy: Assert that changed files and lines are within limits
  * Configuration: Maximum files (default: 50), maximum lines (default: 1000)
  * Strategy: Strategy 11 (VCS Provider API Queries)

---

## Service Catalog Integration

### Catalog Entry Policies

* `catalog-registered` **Service is registered in catalog**: Component must have an entry in the service catalog (Backstage, ServiceNow, etc.).
  * Collector(s): Check for catalog-info.yaml in repository or query catalog API
  * Component JSON:
    * `.catalog.exists` - Boolean indicating catalog registration
    * `.catalog.source.tool` - Catalog system name
    * `.catalog.source.file` - Path to catalog definition file
  * Policy: Assert that catalog entry exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-valid-yaml` **Catalog entry is valid YAML**: The catalog definition file must be syntactically valid.
  * Collector(s): Parse catalog-info.yaml and validate YAML syntax
  * Component JSON:
    * `.catalog.valid` - Boolean indicating YAML validity
    * `.catalog.errors` - Array of validation errors
  * Policy: Assert that catalog file is valid
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-required-fields` **Catalog entry has required fields**: Catalog entry must include mandatory fields (name, description, owner, etc.).
  * Collector(s): Parse catalog file and check for required fields
  * Component JSON:
    * `.catalog.entity.name` - Service name
    * `.catalog.entity.description` - Service description
    * `.catalog.entity.owner` - Service owner
    * `.catalog.entity.type` - Entity type (service, library, etc.)
    * `.catalog.missing_fields` - Array of required fields that are missing
  * Policy: Assert that all required fields are present and non-empty
  * Configuration: List of required fields
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-meaningful-description` **Catalog description is meaningful**: Service description must be substantive, not placeholder text.
  * Collector(s): Extract description from catalog and analyze length/content
  * Component JSON:
    * `.catalog.entity.description` - Service description
    * `.catalog.entity.description_length` - Character count
  * Policy: Assert that description meets minimum length and doesn't match placeholder patterns
  * Configuration: Minimum description length (default: 20), placeholder patterns to reject
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-lifecycle-stage` **Catalog entry has lifecycle stage**: Services must declare their lifecycle stage (production, deprecated, etc.).
  * Collector(s): Extract lifecycle from catalog entry
  * Component JSON:
    * `.catalog.entity.lifecycle` - Lifecycle stage (production, experimental, deprecated)
  * Policy: Assert that lifecycle is defined
  * Configuration: Valid lifecycle values
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-correct-type` **Catalog entry has correct type**: Entity type must be from approved list (service, website, library, etc.).
  * Collector(s): Extract type from catalog entry
  * Component JSON:
    * `.catalog.entity.type` - Entity type
  * Policy: Assert that type is in approved list
  * Configuration: List of valid entity types
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-system-assignment` **Catalog entry has system assignment**: Services should be assigned to a system for grouping.
  * Collector(s): Extract system from catalog entry
  * Component JSON:
    * `.catalog.entity.system` - Parent system name
  * Policy: Assert that system is defined for service-type entities
  * Configuration: Entity types requiring system assignment
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-valid-tags` **Catalog entry has valid tags**: Catalog tags must be from approved taxonomy.
  * Collector(s): Extract tags from catalog and validate against approved list
  * Component JSON:
    * `.catalog.entity.tags` - Array of tags
    * `.catalog.invalid_tags` - Array of tags not in approved list
  * Policy: Assert that all tags are from approved taxonomy
  * Configuration: List of approved tags or tag patterns
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Catalog Annotations

* `catalog-pagerduty-annotation` **Catalog has PagerDuty annotation**: Production services must link to their PagerDuty service.
  * Collector(s): Extract PagerDuty annotation from catalog
  * Component JSON:
    * `.catalog.annotations.pagerduty_service` - PagerDuty service ID
    * `.catalog.annotations.pagerduty_integration_key` - Integration key if applicable
  * Policy: Assert that PagerDuty annotation exists for production services
  * Configuration: Tags requiring PagerDuty integration
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-slack-annotation` **Catalog has Slack channel annotation**: Services should link to their team's Slack channel.
  * Collector(s): Extract Slack annotation from catalog
  * Component JSON:
    * `.catalog.annotations.slack_channel` - Slack channel name or URL
  * Policy: Assert that Slack channel is defined
  * Configuration: Whether this is required or optional
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-repository-link` **Catalog has repository link**: Catalog entry should link back to the source repository.
  * Collector(s): Extract repository annotation from catalog
  * Component JSON:
    * `.catalog.annotations.github_repo` - GitHub repository URL
    * `.catalog.annotations.source_location` - Source code location
  * Policy: Assert that repository link is present and valid
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-declares-dependencies` **Catalog declares dependencies**: Services should declare their runtime dependencies.
  * Collector(s): Extract dependency declarations from catalog
  * Component JSON:
    * `.catalog.dependencies` - Array of dependency names
    * `.catalog.apis.consumes` - Array of consumed APIs
  * Policy: Assert that dependencies are declared (or explicitly empty)
  * Configuration: Entity types requiring dependency declaration
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-declares-apis` **Catalog declares provided APIs**: API-providing services must declare what APIs they offer.
  * Collector(s): Extract API declarations from catalog
  * Component JSON:
    * `.catalog.apis.provides` - Array of provided API names
  * Policy: Assert that API-tagged services declare provided APIs
  * Configuration: Tags requiring API declaration
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `catalog-valid-dependencies` **Catalog dependencies exist in catalog**: Declared dependencies should reference valid catalog entries.
  * Collector(s): Validate dependency references against catalog API
  * Component JSON:
    * `.catalog.dependencies` - Array of declared dependencies
    * `.catalog.invalid_dependencies` - Dependencies not found in catalog
  * Policy: Assert that all dependencies reference valid catalog entries
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Repository Configuration Files

### Standard Files

* `repo-gitignore-exists` **Repository has .gitignore**: Every repository should have a .gitignore file.
  * Collector(s): Check for .gitignore file existence
  * Component JSON:
    * `.repo.files.gitignore` - Boolean indicating .gitignore presence
  * Policy: Assert that .gitignore exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-dockerignore-exists` **Repository has .dockerignore**: Repositories with Dockerfiles should have a .dockerignore file.
  * Collector(s): Check for .dockerignore when Dockerfile is present
  * Component JSON:
    * `.repo.files.dockerignore` - Boolean indicating .dockerignore presence
    * `.containers.definitions` - Array of Dockerfile info (to check if Dockerfiles exist)
  * Policy: Assert that .dockerignore exists when Dockerfiles are present
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-editorconfig` **Repository has .editorconfig**: Repositories should have .editorconfig for consistent formatting.
  * Collector(s): Check for .editorconfig file existence
  * Component JSON:
    * `.repo.files.editorconfig` - Boolean indicating .editorconfig presence
  * Policy: Assert that .editorconfig exists
  * Configuration: Whether this is required or optional
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-license-exists` **Repository has LICENSE file**: Open source or shared repositories must include a license file.
  * Collector(s): Check for LICENSE or LICENSE.md file
  * Component JSON:
    * `.repo.files.license` - Boolean indicating license presence
    * `.repo.license.type` - License type (MIT, Apache, etc.)
    * `.repo.license.path` - Path to license file
  * Policy: Assert that license file exists for applicable repositories
  * Configuration: Tags requiring license (e.g., ["open-source", "shared-library"])
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-approved-license` **Repository has approved LICENSE type**: License must be from organization-approved list.
  * Collector(s): Parse LICENSE file and detect license type
  * Component JSON:
    * `.repo.license.type` - Detected license type
  * Policy: Assert that license type is in approved list
  * Configuration: List of approved license types
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-contributing-guide` **Repository has CONTRIBUTING guide**: Open source or shared repositories should have contribution guidelines.
  * Collector(s): Check for CONTRIBUTING.md file
  * Component JSON:
    * `.repo.files.contributing` - Boolean indicating CONTRIBUTING.md presence
  * Policy: Assert that CONTRIBUTING.md exists for applicable repositories
  * Configuration: Tags requiring contributing guide
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-changelog-exists` **Repository has CHANGELOG**: Libraries and shared packages should maintain a changelog.
  * Collector(s): Check for CHANGELOG.md or similar file
  * Component JSON:
    * `.repo.files.changelog` - Boolean indicating changelog presence
    * `.repo.changelog.path` - Path to changelog file
  * Policy: Assert that changelog exists for libraries and packages
  * Configuration: Tags or types requiring changelog
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-security-md` **Repository has SECURITY.md**: Repositories should document security vulnerability reporting process.
  * Collector(s): Check for SECURITY.md file
  * Component JSON:
    * `.repo.files.security` - Boolean indicating SECURITY.md presence
  * Policy: Assert that SECURITY.md exists
  * Configuration: Whether this is required or optional per tag
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

### Build and Development Files

* `repo-build-script` **Repository has Makefile or standard build script**: Repositories should have a standard way to build locally.
  * Collector(s): Check for Makefile, build.sh, or similar standard build files
  * Component JSON:
    * `.repo.files.makefile` - Boolean indicating Makefile presence
    * `.repo.files.build_script` - Boolean indicating build script presence
    * `.repo.build.method` - Detected build method (make, npm, gradle, etc.)
  * Policy: Assert that a recognized build mechanism exists
  * Configuration: Recognized build files and their priority
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-lockfile` **Repository has lock file for dependencies**: Package managers should have lock files committed for reproducible builds.
  * Collector(s): Detect language/ecosystem and check for corresponding lock file
  * Component JSON:
    * `.repo.files.package_lock` - Boolean for npm package-lock.json
    * `.repo.files.yarn_lock` - Boolean for yarn.lock
    * `.repo.files.go_sum` - Boolean for go.sum
    * `.repo.files.poetry_lock` - Boolean for poetry.lock
    * `.dependencies.lock_file_exists` - Boolean indicating appropriate lock file exists
  * Policy: Assert that lock file exists for detected package manager
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-pre-commit` **Repository has pre-commit configuration**: Repositories should use pre-commit hooks for local validation.
  * Collector(s): Check for .pre-commit-config.yaml or similar
  * Component JSON:
    * `.repo.files.pre_commit_config` - Boolean indicating pre-commit config presence
  * Policy: Assert that pre-commit configuration exists
  * Configuration: Whether this is required or optional
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-ci-config` **Repository has CI configuration**: Repositories should have CI/CD pipeline configuration.
  * Collector(s): Check for CI config files (.github/workflows/, .gitlab-ci.yml, Jenkinsfile, etc.)
  * Component JSON:
    * `.ci.config_exists` - Boolean indicating CI configuration presence
    * `.ci.platform` - Detected CI platform
    * `.ci.config_files` - Array of CI config file paths
  * Policy: Assert that CI configuration exists
  * Configuration: None
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-formatter-config` **Repository has code formatting configuration**: Repositories should have formatter configuration (prettier, black, gofmt, etc.).
  * Collector(s): Detect language and check for corresponding formatter config
  * Component JSON:
    * `.repo.files.prettierrc` - Boolean for prettier config
    * `.repo.files.black_config` - Boolean for black config in pyproject.toml
    * `.repo.formatter_config_exists` - Boolean indicating formatter is configured
  * Policy: Assert that formatter configuration exists for the detected language
  * Configuration: Required formatter configs per language
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-linter-config` **Repository has linter configuration**: Repositories should have linter configuration (eslint, pylint, golangci-lint, etc.).
  * Collector(s): Detect language and check for corresponding linter config
  * Component JSON:
    * `.repo.files.eslintrc` - Boolean for ESLint config
    * `.repo.files.pylintrc` - Boolean for pylint config
    * `.repo.files.golangci` - Boolean for golangci-lint config
    * `.repo.linter_config_exists` - Boolean indicating linter is configured
  * Policy: Assert that linter configuration exists for the detected language
  * Configuration: Required linter configs per language
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

---

## Repository Hygiene

### Repository Settings

* `vcs-default-branch-name` **Default branch is named correctly**: Repository should use approved default branch naming (main, master).
  * Collector(s): Query VCS API for default branch name
  * Component JSON:
    * `.vcs.default_branch` - Default branch name
  * Policy: Assert that default branch name is in approved list
  * Configuration: Approved branch names (default: ["main"])
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-repo-description` **Repository has description**: Repository should have a description set in the VCS platform.
  * Collector(s): Query VCS API for repository description
  * Component JSON:
    * `.vcs.description` - Repository description
    * `.vcs.has_description` - Boolean indicating description is set
  * Policy: Assert that repository description is not empty
  * Configuration: Minimum description length
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-repo-topics` **Repository has topics/tags**: Repository should be tagged with appropriate topics in the VCS platform.
  * Collector(s): Query VCS API for repository topics
  * Component JSON:
    * `.vcs.topics` - Array of repository topics
    * `.vcs.has_topics` - Boolean indicating topics are set
  * Policy: Assert that repository has at least one topic
  * Configuration: Required topics or minimum topic count
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-visibility` **Repository visibility is appropriate**: Repository visibility (public/private/internal) should match organizational requirements.
  * Collector(s): Query VCS API for repository visibility
  * Component JSON:
    * `.vcs.visibility` - Repository visibility level
  * Policy: Assert that visibility matches expected value based on tags
  * Configuration: Visibility requirements per tag (e.g., PCI services must be private)
  * Strategy: Strategy 11 (VCS Provider API Queries)

* `vcs-limited-pushers` **Repository has limited direct pushers**: Only approved users/teams should be able to push directly.
  * Collector(s): Query VCS API for push access permissions
  * Component JSON:
    * `.vcs.permissions.direct_push_users` - Users with direct push access
    * `.vcs.permissions.direct_push_teams` - Teams with direct push access
  * Policy: Assert that direct pushers are within approved list or count limit
  * Configuration: Maximum direct pushers, approved teams
  * Strategy: Strategy 11 (VCS Provider API Queries)

### File and Content Hygiene

* `repo-no-large-files` **No large files committed**: Repository should not contain excessively large files.
  * Collector(s): Scan repository for files exceeding size threshold
  * Component JSON:
    * `.repo.large_files` - Array of files exceeding threshold with sizes
    * `.repo.has_large_files` - Boolean indicating large files present
  * Policy: Assert that no large files exist
  * Configuration: Maximum file size (default: 10MB), excluded paths
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-no-binaries-in-src` **No binary files in source directories**: Binary files should not be committed to source code directories.
  * Collector(s): Scan for binary files in source directories
  * Component JSON:
    * `.repo.binary_files` - Array of binary files found in source dirs
    * `.repo.has_source_binaries` - Boolean indicating binaries in source
  * Policy: Assert that no binaries exist in source directories
  * Configuration: Source directory patterns, excluded file types
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-no-sensitive-files` **No sensitive file patterns**: Repository should not contain files matching sensitive patterns (.env, secrets.yaml, etc.).
  * Collector(s): Scan for files matching sensitive patterns
  * Component JSON:
    * `.repo.sensitive_files` - Array of potentially sensitive files found
    * `.repo.has_sensitive_files` - Boolean indicating sensitive files present
  * Policy: Assert that no sensitive file patterns are found
  * Configuration: Sensitive file patterns to check for
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-not-stale` **Repository is not stale**: Repository should have recent activity indicating active maintenance.
  * Collector(s): Query VCS API for last commit date
  * Component JSON:
    * `.vcs.last_commit_date` - ISO 8601 timestamp of last commit
    * `.vcs.days_since_last_commit` - Days since last commit
  * Policy: Assert that days since last commit is within threshold
  * Configuration: Maximum days without commits (default: 180)
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)

* `repo-file-naming-convention` **Repository has consistent file naming**: Files should follow naming conventions (lowercase, no spaces, etc.).
  * Collector(s): Scan repository for files violating naming conventions
  * Component JSON:
    * `.repo.naming_violations` - Array of files violating naming rules
    * `.repo.naming_compliant` - Boolean indicating all files comply
  * Policy: Assert that all files follow naming conventions
  * Configuration: Naming rules regex patterns, excluded directories
  * Strategy: Strategy 8 (File Parsing and Schema Extraction)
