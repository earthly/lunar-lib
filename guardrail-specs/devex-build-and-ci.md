# DevEx, Build and CI Guardrails

This document specifies possible policies for the **DevEx, Build and CI** category. These guardrails cover golden path standards (approved runtimes, frameworks, and templates), dependency management (pinning, EOL, and restricted libraries), container image standards, build quality and reproducibility, CI/CD pipeline requirements, artifact management, and developer experience tooling.

---

## Golden Paths and Project Standards

### Language and Runtime Versions

* **Language version meets minimum requirements**: Projects must use a supported version of their primary programming language, not EOL or deprecated versions.
  * Collector(s): Parse language version files (.go-version, .python-version, .nvmrc, .ruby-version, .java-version) and configuration files (go.mod, pyproject.toml, package.json engines, pom.xml)
  * Component JSON:
    * `.lang.<language>.version` - Detected language version
    * `.lang.<language>.version_source` - Where version was detected (file name)
    * `.lang.<language>.meets_minimum` - Boolean indicating version meets minimum
    * `.lang.<language>.is_eol` - Boolean indicating version is end-of-life
  * Policy: Assert that language version is at or above the configured minimum and not EOL
  * Configuration: Minimum version per language (e.g., Go: 1.21, Python: 3.10, Node: 18), EOL version list

* **Runtime version is explicitly specified**: Projects must explicitly declare their runtime version for reproducibility, not rely on system defaults.
  * Collector(s): Check for presence of version specification files (.go-version, .python-version, .nvmrc, .tool-versions, etc.)
  * Component JSON:
    * `.lang.<language>.version_specified` - Boolean indicating version is explicitly declared
    * `.lang.<language>.version_file` - Path to version specification file
  * Policy: Assert that language version is explicitly specified
  * Configuration: Required version file patterns per language

* **Language version file is in approved format**: Version specification should use approved file formats (e.g., .tool-versions for asdf, or language-specific files).
  * Collector(s): Detect version file format and validate against approved formats
  * Component JSON:
    * `.lang.<language>.version_file_format` - Format of version file used
    * `.lang.<language>.uses_approved_format` - Boolean for approved format
  * Policy: Assert that version is specified using approved file format
  * Configuration: Approved version file formats (e.g., [".tool-versions", ".go-version"])

### Framework and Library Compliance

* **Project uses approved web framework**: Web services must use organization-approved frameworks to ensure consistent security and maintainability.
  * Collector(s): Detect web framework from dependencies and import statements (language-specific: Go: gin/echo/fiber, Python: flask/django/fastapi, Node: express/nestjs/fastify, Java: spring/quarkus)
  * Component JSON:
    * `.lang.<language>.framework` - Detected framework name
    * `.lang.<language>.framework_version` - Framework version
    * `.lang.<language>.uses_approved_framework` - Boolean for approved framework
  * Policy: Assert that detected framework is from approved list
  * Configuration: Approved frameworks per language

* **Project uses approved ORM or database library**: Database access should use standard libraries for consistent patterns and security.
  * Collector(s): Detect database libraries from dependencies (GORM, SQLAlchemy, Prisma, Hibernate, etc.)
  * Component JSON:
    * `.lang.<language>.database_library` - Detected database library
    * `.lang.<language>.uses_approved_db_library` - Boolean for approved library
  * Policy: Assert that database library is from approved list
  * Configuration: Approved database libraries per language

* **Project uses approved HTTP client library**: HTTP clients should use vetted libraries with proper timeout and retry handling.
  * Collector(s): Detect HTTP client libraries from dependencies and imports
  * Component JSON:
    * `.lang.<language>.http_client` - Detected HTTP client library
    * `.lang.<language>.uses_approved_http_client` - Boolean for approved library
  * Policy: Assert that HTTP client is from approved list
  * Configuration: Approved HTTP client libraries per language

* **Project uses approved logging library**: Logging should use organizational standard libraries for consistent format and integration.
  * Collector(s): Detect logging library from dependencies and imports
  * Component JSON:
    * `.lang.<language>.logging_library` - Detected logging library
    * `.lang.<language>.uses_approved_logging` - Boolean for approved library
  * Policy: Assert that logging library is from approved list
  * Configuration: Approved logging libraries per language

### Project Templates and Structure

* **Project follows golden path template**: New projects should be created from organization-approved templates to ensure standard structure.
  * Collector(s): Check for template markers (e.g., .golden-path.yml, template origin in git history, or structural pattern matching)
  * Component JSON:
    * `.repo.template.used` - Boolean indicating template was used
    * `.repo.template.name` - Template name if detected
    * `.repo.template.version` - Template version if applicable
  * Policy: Assert that project was created from an approved template (may be advisory for legacy projects)
  * Configuration: Approved template names, grace period for legacy projects

* **Project structure follows standard layout**: Project directory structure must follow language-specific conventions (Go: cmd/, pkg/, internal/; Python: src/ layout; Node: src/, lib/).
  * Collector(s): Analyze directory structure and compare against language-specific standard layouts
  * Component JSON:
    * `.repo.structure.follows_standard` - Boolean for standard structure
    * `.repo.structure.layout_type` - Detected layout type
    * `.repo.structure.deviations` - Array of deviations from standard
  * Policy: Assert that project structure follows standard layout
  * Configuration: Standard layouts per language

* **Makefile or build script exists with standard targets**: Projects must have a Makefile or equivalent with standard targets (build, test, lint, clean).
  * Collector(s): Check for Makefile, justfile, or package.json scripts; extract available targets
  * Component JSON:
    * `.repo.build_system.exists` - Boolean for build system presence
    * `.repo.build_system.type` - Type of build system (make, just, npm-scripts, gradle)
    * `.repo.build_system.targets` - Array of available targets
    * `.repo.build_system.has_required_targets` - Boolean for required targets present
  * Policy: Assert that standard build targets are available
  * Configuration: Required targets (default: ["build", "test", "lint"])

### Configuration Files and Standards

* **EditorConfig file exists**: Projects must have .editorconfig for consistent formatting across editors.
  * Collector(s): Check for .editorconfig file existence and validate content
  * Component JSON:
    * `.repo.files.editorconfig` - Boolean indicating .editorconfig exists
    * `.repo.editorconfig.valid` - Boolean for valid configuration
  * Policy: Assert that .editorconfig exists
  * Configuration: None

* **Linter configuration exists and is valid**: Projects must have linter configuration using organizational standards.
  * Collector(s): Check for linter configuration files (language-specific: .golangci.yml, .eslintrc.*, .flake8, .pylintrc, checkstyle.xml)
  * Component JSON:
    * `.lang.<language>.linter.configured` - Boolean for linter configuration
    * `.lang.<language>.linter.config_file` - Path to linter configuration
    * `.lang.<language>.linter.extends_org_config` - Boolean indicating org config is extended
  * Policy: Assert that linter is configured with organizational standards
  * Configuration: Required linter per language, org config package names

* **Formatter configuration exists and is valid**: Projects must have code formatter configuration using organizational standards.
  * Collector(s): Check for formatter configuration files (prettier, black, gofmt, google-java-format)
  * Component JSON:
    * `.lang.<language>.formatter.configured` - Boolean for formatter configuration
    * `.lang.<language>.formatter.config_file` - Path to formatter configuration
    * `.lang.<language>.formatter.tool` - Formatter tool name
  * Policy: Assert that formatter is configured
  * Configuration: Required formatter per language

* **Pre-commit hooks are configured**: Projects should have pre-commit hooks for automated quality checks before commit.
  * Collector(s): Check for pre-commit configuration (.pre-commit-config.yaml, .husky/, lefthook.yml)
  * Component JSON:
    * `.repo.pre_commit.configured` - Boolean for pre-commit configuration
    * `.repo.pre_commit.tool` - Pre-commit tool used (pre-commit, husky, lefthook)
    * `.repo.pre_commit.hooks` - Array of configured hooks
  * Policy: Assert that pre-commit hooks are configured
  * Configuration: Required hooks (e.g., ["lint", "format", "test"])

---

## Dependency Management

### Version Pinning and Lock Files

* **Lock file exists for dependencies**: Projects must have a dependency lock file to ensure reproducible builds.
  * Collector(s): Check for lock files (go.sum, package-lock.json, yarn.lock, Pipfile.lock, poetry.lock, Cargo.lock, Gemfile.lock, pom.xml.sha1)
  * Component JSON:
    * `.dependencies.lock_file.exists` - Boolean indicating lock file exists
    * `.dependencies.lock_file.path` - Path to lock file
    * `.dependencies.lock_file.type` - Lock file type
  * Policy: Assert that appropriate lock file exists for the project's package manager
  * Configuration: None

* **Lock file is committed and up-to-date**: Lock file must be committed to version control and in sync with dependency manifest.
  * Collector(s): Check lock file is tracked in git and compare timestamps/hashes with manifest
  * Component JSON:
    * `.dependencies.lock_file.committed` - Boolean for lock file in git
    * `.dependencies.lock_file.in_sync` - Boolean indicating lock file matches manifest
    * `.dependencies.lock_file.stale` - Boolean for outdated lock file
  * Policy: Assert that lock file is committed and in sync with manifest
  * Configuration: None

* **Dependencies use exact versions, not ranges**: Direct dependencies should specify exact versions, not version ranges, for reproducibility.
  * Collector(s): Parse dependency manifest and check version specifications (npm: no ^/~, Python: ==, Go: exact versions)
  * Component JSON:
    * `.dependencies.exact_versions` - Boolean indicating all direct deps use exact versions
    * `.dependencies.range_versions` - Array of dependencies using version ranges
    * `.dependencies.range_version_count` - Count of range-versioned dependencies
  * Policy: Assert that all direct dependencies use exact versions
  * Configuration: Allowed exceptions (e.g., peer dependencies)

* **Dependency manifest does not contain floating versions**: Dependencies must not use "latest", "*", or other floating version specifiers.
  * Collector(s): Parse dependency manifest for floating version patterns
  * Component JSON:
    * `.dependencies.floating_versions` - Array of dependencies with floating versions
    * `.dependencies.has_floating_versions` - Boolean for floating version presence
  * Policy: Assert that no floating versions are used
  * Configuration: None

### End-of-Life and Deprecated Dependencies

* **No dependencies at end-of-life**: Dependencies must not be EOL/unmaintained; projects should use actively maintained versions.
  * Collector(s): Cross-reference dependencies with endoflife.date API or internal EOL database
  * Component JSON:
    * `.dependencies.eol.count` - Number of EOL dependencies
    * `.dependencies.eol.packages` - Array of EOL package details (name, version, eol_date)
    * `.dependencies.has_eol` - Boolean for EOL dependency presence
  * Policy: Assert that no dependencies are end-of-life
  * Configuration: EOL data source, grace period after EOL date

* **No deprecated dependencies**: Dependencies that are marked deprecated by maintainers should be replaced.
  * Collector(s): Check package registries for deprecation flags (npm deprecation, PyPI classifiers, Maven deprecation)
  * Component JSON:
    * `.dependencies.deprecated.count` - Number of deprecated dependencies
    * `.dependencies.deprecated.packages` - Array of deprecated packages
    * `.dependencies.has_deprecated` - Boolean for deprecated presence
  * Policy: Assert that no dependencies are deprecated
  * Configuration: Allow specific deprecated packages with justification

* **Dependencies are within support window**: Dependencies should be on versions still receiving security updates from maintainers.
  * Collector(s): Check version against known support windows for major dependencies
  * Component JSON:
    * `.dependencies.unsupported.count` - Number of unsupported dependency versions
    * `.dependencies.unsupported.packages` - Array of unsupported packages
    * `.dependencies.has_unsupported` - Boolean for unsupported presence
  * Policy: Assert that dependencies are within support windows
  * Configuration: Support window definitions for key packages

### Restricted and Forbidden Libraries

* **No restricted libraries are used**: Certain libraries are forbidden due to security, licensing, or organizational policy.
  * Collector(s): Compare dependency list against restricted library database
  * Component JSON:
    * `.dependencies.restricted.count` - Number of restricted dependencies found
    * `.dependencies.restricted.packages` - Array of restricted packages with reason
    * `.dependencies.has_restricted` - Boolean for restricted presence
  * Policy: Assert that no restricted libraries are present
  * Configuration: Restricted package list with reasons (e.g., {"lodash": "use lodash-es instead"})

* **License compatibility is verified**: All dependencies must have licenses compatible with organizational policy.
  * Collector(s): Extract license information from dependencies and SBOM; validate against approved list
  * Component JSON:
    * `.dependencies.licenses.all` - Array of all licenses found
    * `.dependencies.licenses.incompatible` - Array of packages with incompatible licenses
    * `.dependencies.licenses.unknown` - Array of packages with unknown licenses
    * `.dependencies.licenses.compliant` - Boolean for all licenses compliant
  * Policy: Assert that all dependency licenses are approved
  * Configuration: Approved license list (e.g., ["MIT", "Apache-2.0", "BSD-3-Clause"])

* **No duplicate/redundant dependencies**: Projects should not have multiple libraries serving the same purpose (e.g., multiple date libraries).
  * Collector(s): Analyze dependencies for functional overlap
  * Component JSON:
    * `.dependencies.duplicates` - Array of duplicate function groups (e.g., ["moment", "date-fns"])
    * `.dependencies.has_duplicates` - Boolean for duplicate presence
  * Policy: Assert that no redundant dependencies exist
  * Configuration: Duplicate detection rules (e.g., date libraries, HTTP clients)

### Dependency Sources

* **Dependencies are fetched from approved registries**: All dependencies must come from approved package registries (internal artifactory, npmjs, PyPI, etc.).
  * Collector(s): Analyze package manager configuration for registry URLs; check lock files for registry sources
  * Component JSON:
    * `.dependencies.registries` - Array of registries used
    * `.dependencies.unapproved_registries` - Array of unapproved registries found
    * `.dependencies.uses_approved_registries` - Boolean for approved registries only
  * Policy: Assert that all dependencies come from approved registries
  * Configuration: Approved registry URLs per ecosystem

* **Private dependencies reference internal registry**: Internal/private packages must be resolved from internal registries, not public mirrors.
  * Collector(s): Check package manager configuration for internal package routing
  * Component JSON:
    * `.dependencies.internal.configured` - Boolean for internal registry configuration
    * `.dependencies.internal.packages` - Array of internal packages
    * `.dependencies.internal.correctly_sourced` - Boolean for correct sourcing
  * Policy: Assert that internal packages use internal registry
  * Configuration: Internal package patterns, internal registry URL

* **No git dependencies in production**: Production code should not depend on git URLs; use published packages.
  * Collector(s): Parse dependency manifest for git:// or github: dependencies
  * Component JSON:
    * `.dependencies.git_dependencies` - Array of git-sourced dependencies
    * `.dependencies.has_git_dependencies` - Boolean for git dependency presence
  * Policy: Assert that no git dependencies are used in production
  * Configuration: Allowed exceptions for internal packages in transition

---

## Container Image Standards

### Base Image Requirements

* **Container uses approved base images**: Dockerfiles must use base images from the approved list (distroless, alpine, organization-blessed images).
  * Collector(s): Parse Dockerfiles for FROM instructions and extract base images
  * Component JSON:
    * `.containers.definitions[].base_images` - Array of base images used
    * `.containers.unapproved_base_images` - Array of unapproved base images
    * `.containers.uses_approved_base_images` - Boolean for all approved
  * Policy: Assert that all base images are from approved list
  * Configuration: Approved base image patterns (e.g., ["gcr.io/distroless/*", "*-alpine", "internal.registry/*"])

* **Base image uses specific tag, not latest**: Base images must specify version tags, not :latest or implicit latest.
  * Collector(s): Parse Dockerfile FROM instructions for tag presence
  * Component JSON:
    * `.containers.definitions[].base_images[].is_latest` - Boolean for latest tag
    * `.containers.definitions[].base_images[].tag` - Tag value
    * `.containers.summary.uses_latest_tag` - Boolean for any latest usage
  * Policy: Assert that no base images use :latest tag
  * Configuration: None

* **Base image uses digest for immutability**: Production images should pin base images by digest for complete reproducibility.
  * Collector(s): Parse Dockerfile FROM instructions for digest references (@sha256:...)
  * Component JSON:
    * `.containers.definitions[].base_images[].is_pinned` - Boolean for digest pinning
    * `.containers.definitions[].base_images[].digest` - Digest value if present
    * `.containers.summary.all_pinned_by_digest` - Boolean for all pinned
  * Policy: Assert that base images are pinned by digest (may be advisory or required for production)
  * Configuration: Tags requiring digest pinning (e.g., ["production", "tier1"])

* **Final stage uses minimal base image**: Multi-stage builds should use minimal images (distroless, scratch, alpine) for the final stage.
  * Collector(s): Parse Dockerfile for multi-stage builds and analyze final stage base image
  * Component JSON:
    * `.containers.definitions[].final_stage.base_image` - Final stage base image
    * `.containers.definitions[].final_stage.is_minimal` - Boolean for minimal image
  * Policy: Assert that final stage uses minimal base image
  * Configuration: Minimal image patterns

### Registry and Publishing Standards

* **Images are pushed to approved registries**: Container images must only be pushed to organization-approved registries.
  * Collector(s): Capture container push operations in CI and extract target registries
  * Component JSON:
    * `.containers.builds[].registry` - Registry where image was pushed
    * `.containers.registries_used` - Array of all registries used
    * `.containers.uses_approved_registries` - Boolean for approved registries only
  * Policy: Assert that images are pushed only to approved registries
  * Configuration: Approved registry patterns

* **Images are not pushed to public registries**: Production images must not be pushed to public registries like Docker Hub.
  * Collector(s): Detect pushes to known public registries
  * Component JSON:
    * `.containers.builds[].is_public_registry` - Boolean for public registry
    * `.containers.pushed_to_public` - Boolean for any public push
  * Policy: Assert that no images are pushed to public registries
  * Configuration: Public registry patterns to block

* **Image repository naming follows conventions**: Image names should follow organization naming conventions (e.g., org/team/service).
  * Collector(s): Extract image names from CI push operations and validate format
  * Component JSON:
    * `.containers.builds[].image` - Full image reference
    * `.containers.builds[].follows_naming_convention` - Boolean for convention compliance
  * Policy: Assert that image names follow naming conventions
  * Configuration: Naming convention pattern

### Image Labels and Metadata

* **Container images have required OCI labels**: Images must include standard OCI labels for traceability (source, version, vendor, etc.).
  * Collector(s): Parse Dockerfile LABEL instructions or inspect built images for OCI labels
  * Component JSON:
    * `.containers.definitions[].labels` - Object of label key-value pairs
    * `.containers.definitions[].has_required_labels` - Boolean for required labels present
    * `.containers.definitions[].missing_labels` - Array of missing required labels
  * Policy: Assert that all required OCI labels are present
  * Configuration: Required labels (default: ["org.opencontainers.image.source", "org.opencontainers.image.version", "org.opencontainers.image.revision"])

* **Container image includes git SHA label**: Images must include the git commit SHA that produced them for traceability.
  * Collector(s): Check for git SHA in image labels (org.opencontainers.image.revision or custom)
  * Component JSON:
    * `.containers.builds[].has_git_sha_label` - Boolean for git SHA label
    * `.containers.builds[].git_sha` - Git SHA value in label
  * Policy: Assert that images include git SHA label
  * Configuration: Label key for git SHA

* **Container image includes build timestamp**: Images should include build timestamp for age verification.
  * Collector(s): Check for creation timestamp in image metadata
  * Component JSON:
    * `.containers.builds[].has_timestamp` - Boolean for timestamp presence
    * `.containers.builds[].created_at` - Image creation timestamp
  * Policy: Assert that images include build timestamp
  * Configuration: None

### Image Tagging Practices

* **Images use semantic version tags**: Production images should use semantic version tags (v1.2.3), not arbitrary strings.
  * Collector(s): Extract image tags from CI push operations and validate semver format
  * Component JSON:
    * `.containers.builds[].tag` - Image tag
    * `.containers.builds[].is_semver` - Boolean for semver format
  * Policy: Assert that production images use semantic versioning
  * Configuration: Tags requiring semver (e.g., ["production", "release"])

* **Git SHA is included in image tag or label**: Every image should be traceable to source via git SHA in tag or label.
  * Collector(s): Check image tag for git SHA component or verify label presence
  * Component JSON:
    * `.containers.builds[].tag_contains_sha` - Boolean for SHA in tag
    * `.containers.builds[].traceable_to_source` - Boolean for any traceability method
  * Policy: Assert that images are traceable to source
  * Configuration: None

* **Mutable tags are not overwritten**: Tags like :latest or :main should follow immutability practices (tag once, never overwrite).
  * Collector(s): Check registry for tag overwrites or enforce digest-based references
  * Component JSON:
    * `.containers.builds[].tag_is_immutable` - Boolean for immutable tagging
    * `.containers.tag_policy` - Tag policy in use (immutable, mutable-allowed)
  * Policy: Assert that mutable tags follow immutability policy
  * Configuration: Enforce immutable tags (boolean)

---

## Build Configuration and Quality

### Build Reproducibility

* **Build is reproducible**: Building the same source should produce identical artifacts (binary, image, package).
  * Collector(s): Compare artifact hashes from multiple builds of same source, or verify reproducibility markers
  * Component JSON:
    * `.build.reproducible.verified` - Boolean for reproducibility verified
    * `.build.reproducible.method` - Verification method (hash-comparison, attestation)
    * `.build.artifact_hash` - Hash of produced artifact
  * Policy: Assert that builds are reproducible
  * Configuration: Tags requiring reproducibility verification

* **Build uses pinned tool versions**: Build tools (compilers, bundlers) should use pinned versions, not floating.
  * Collector(s): Analyze CI configuration and build scripts for tool version specifications
  * Component JSON:
    * `.build.tools.pinned` - Boolean for pinned tool versions
    * `.build.tools.versions` - Object of tool versions
    * `.build.tools.floating` - Array of tools with floating versions
  * Policy: Assert that build tools use pinned versions
  * Configuration: None

* **Build does not depend on ambient environment**: Builds should not rely on environment variables or system state not explicitly declared.
  * Collector(s): Analyze build configuration for undeclared environment dependencies
  * Component JSON:
    * `.build.environment.declared_vars` - Array of declared environment variables
    * `.build.environment.implicit_vars` - Array of implicitly used variables
    * `.build.environment.fully_declared` - Boolean for full declaration
  * Policy: Assert that build environment is fully declared
  * Configuration: Allowed implicit variables (e.g., ["CI", "HOME"])

### Build Caching and Performance

* **Build uses layer caching effectively**: Docker builds should use layer caching patterns to speed up builds.
  * Collector(s): Analyze Dockerfile for caching best practices (COPY package files before source, multi-stage builds)
  * Component JSON:
    * `.containers.definitions[].cache_optimized` - Boolean for cache optimization
    * `.containers.definitions[].cache_issues` - Array of caching anti-patterns
  * Policy: Assert that Dockerfiles follow caching best practices
  * Configuration: None

* **Build time is within acceptable limits**: Build time should not exceed configured thresholds for fast feedback.
  * Collector(s): Capture build duration from CI pipeline metrics
  * Component JSON:
    * `.build.duration_seconds` - Build duration in seconds
    * `.build.duration_exceeded` - Boolean for exceeded threshold
  * Policy: Assert that build time is within limits
  * Configuration: Maximum build duration in seconds (default: 600)

* **Build uses CI caching**: CI pipelines should use caching for dependencies and build artifacts.
  * Collector(s): Analyze CI configuration for cache directives
  * Component JSON:
    * `.ci.caching.enabled` - Boolean for CI caching enabled
    * `.ci.caching.paths` - Array of cached paths
    * `.ci.caching.hit_rate` - Cache hit rate if available
  * Policy: Assert that CI caching is configured
  * Configuration: None

### Build Security

* **Build runs in isolated environment**: Builds should run in clean, isolated environments (containers, VMs) to prevent contamination.
  * Collector(s): Check CI configuration for isolation settings (container jobs, ephemeral runners)
  * Component JSON:
    * `.build.isolated` - Boolean for isolated build environment
    * `.build.isolation_method` - Isolation method (container, vm, ephemeral)
  * Policy: Assert that builds run in isolated environments
  * Configuration: None

* **Build dependencies are verified**: Downloaded dependencies should be verified via checksums or signatures.
  * Collector(s): Check package manager configuration for integrity verification settings
  * Component JSON:
    * `.build.dependencies_verified` - Boolean for dependency verification
    * `.build.verification_method` - Verification method (checksum, signature)
  * Policy: Assert that dependency integrity is verified during build
  * Configuration: None

* **No network access during build (hermetic build)**: Builds should not access the network after dependency resolution for reproducibility.
  * Collector(s): Analyze build configuration for network isolation; detect network calls during build phase
  * Component JSON:
    * `.build.hermetic` - Boolean for hermetic build
    * `.build.network_access.allowed` - Boolean for network access allowed
    * `.build.network_access.hosts` - Array of hosts accessed during build
  * Policy: Assert that builds are hermetic (no network access)
  * Configuration: Tags requiring hermetic builds, allowed hosts

---

## CI Pipeline Standards

### Pipeline Configuration

* **CI configuration file exists and is valid**: Projects must have valid CI configuration for automated builds.
  * Collector(s): Check for CI configuration files (.github/workflows/*.yml, .buildkite/pipeline.yml, Jenkinsfile, .gitlab-ci.yml)
  * Component JSON:
    * `.ci.config.exists` - Boolean for CI config presence
    * `.ci.config.path` - Path to CI configuration
    * `.ci.config.valid` - Boolean for valid configuration (syntax)
    * `.ci.platform` - CI platform name
  * Policy: Assert that CI configuration exists and is valid
  * Configuration: None

* **CI configuration uses reusable workflows**: CI should use organization shared/reusable workflows where available.
  * Collector(s): Parse CI configuration for references to shared workflows or templates
  * Component JSON:
    * `.ci.config.uses_shared_workflows` - Boolean for shared workflow usage
    * `.ci.config.shared_workflows` - Array of shared workflows referenced
  * Policy: Assert that CI uses organization shared workflows
  * Configuration: Required shared workflow patterns

* **CI environment variables are from approved sources**: CI secrets and environment variables should come from approved secret management.
  * Collector(s): Analyze CI configuration for secret/variable sources
  * Component JSON:
    * `.ci.secrets.sources` - Array of secret sources used
    * `.ci.secrets.uses_approved_sources` - Boolean for approved sources
  * Policy: Assert that secrets come from approved sources
  * Configuration: Approved secret sources (e.g., ["vault", "github-secrets", "aws-secrets-manager"])

### Required Pipeline Steps

* **Lint step runs in CI**: CI pipeline must include a linting step.
  * Collector(s): Detect lint step execution in CI configuration or pipeline run
  * Component JSON:
    * `.ci.steps_executed.lint` - Boolean for lint step execution
    * `.ci.lint.tool` - Linting tool used
    * `.ci.lint.passed` - Boolean for lint passing
  * Policy: Assert that linting runs in CI
  * Configuration: None

* **Format check runs in CI**: CI pipeline should verify code formatting.
  * Collector(s): Detect format check step execution in CI
  * Component JSON:
    * `.ci.steps_executed.format_check` - Boolean for format check execution
    * `.ci.format.tool` - Formatting tool used
    * `.ci.format.passed` - Boolean for format check passing
  * Policy: Assert that format checking runs in CI
  * Configuration: None

* **Build step runs in CI**: CI pipeline must include a build step for compiled languages.
  * Collector(s): Detect build step execution in CI configuration or pipeline run
  * Component JSON:
    * `.ci.steps_executed.build` - Boolean for build step execution
    * `.ci.build.passed` - Boolean for build success
  * Policy: Assert that build step runs in CI for applicable projects
  * Configuration: Tags requiring build step (compiled languages)

* **Test step runs in CI**: CI pipeline must include test execution.
  * Collector(s): Detect test step execution in CI configuration or pipeline run
  * Component JSON:
    * `.ci.steps_executed.unit_test` - Boolean for unit test execution
    * `.testing.all_passing` - Boolean for all tests passing
  * Policy: Assert that tests run in CI
  * Configuration: None

* **Security scan runs in CI**: CI pipeline must include security scanning (SAST, SCA, or equivalent).
  * Collector(s): Detect security scanning step execution in CI
  * Component JSON:
    * `.ci.steps_executed.security_scan` - Boolean for security scan execution
    * `.sast` - SAST scan data (presence indicates execution)
    * `.sca` - SCA scan data (presence indicates execution)
  * Policy: Assert that security scanning runs in CI
  * Configuration: Required scan types (default: ["sast", "sca"])

### Pipeline Performance and Quality

* **CI pipeline completes within time limit**: Full CI pipeline should complete within configured threshold for fast feedback.
  * Collector(s): Capture CI pipeline duration from CI platform
  * Component JSON:
    * `.ci.run.duration_seconds` - Total pipeline duration
    * `.ci.run.duration_exceeded` - Boolean for exceeded threshold
  * Policy: Assert that CI pipeline completes within time limit
  * Configuration: Maximum pipeline duration in seconds (default: 900)

* **CI pipeline has consistent success rate**: Pipeline should not have high failure rates indicating flaky tests or infrastructure issues.
  * Collector(s): Query CI platform for recent pipeline success/failure rates
  * Component JSON:
    * `.ci.performance.success_rate` - Success rate percentage
    * `.ci.performance.recent_failures` - Number of recent failures
    * `.ci.performance.is_stable` - Boolean for stable pipeline
  * Policy: Assert that CI success rate meets threshold
  * Configuration: Minimum success rate (default: 90%)

* **CI uses parallelization effectively**: Long-running steps should be parallelized to reduce total duration.
  * Collector(s): Analyze CI configuration for parallel job definitions
  * Component JSON:
    * `.ci.parallelization.enabled` - Boolean for parallel execution
    * `.ci.parallelization.max_parallel` - Maximum parallel jobs
  * Policy: Assert that CI uses parallelization where beneficial
  * Configuration: None (advisory)

### Pipeline Security

* **CI does not expose secrets in logs**: CI configuration should mask secrets to prevent log exposure.
  * Collector(s): Check CI configuration for secret masking settings; scan logs for potential secret exposure
  * Component JSON:
    * `.ci.security.secrets_masked` - Boolean for secret masking enabled
    * `.ci.security.potential_exposures` - Array of potential secret exposures
  * Policy: Assert that secrets are masked in CI
  * Configuration: None

* **CI runs with minimal permissions**: CI jobs should use least-privilege principles for permissions.
  * Collector(s): Analyze CI configuration for permission declarations
  * Component JSON:
    * `.ci.security.permissions` - Object of declared permissions
    * `.ci.security.uses_minimal_permissions` - Boolean for minimal permissions
  * Policy: Assert that CI uses minimal permissions
  * Configuration: Maximum allowed permissions

* **CI uses approved runner images**: CI jobs should run on approved runner images/environments.
  * Collector(s): Extract runner image/environment from CI configuration
  * Component JSON:
    * `.ci.runner.image` - Runner image used
    * `.ci.runner.uses_approved_image` - Boolean for approved image
  * Policy: Assert that CI uses approved runner images
  * Configuration: Approved runner image patterns

---

## Artifact Management

### Artifact Signing and Verification

* **Build artifacts are signed**: Published artifacts (images, packages, binaries) must be cryptographically signed.
  * Collector(s): Detect signing step in CI; verify signature presence on artifacts
  * Component JSON:
    * `.artifacts.signed` - Boolean for artifact signing
    * `.artifacts.signature_type` - Signing method (cosign, gpg, sigstore)
    * `.artifacts.signature_verified` - Boolean for verified signature
  * Policy: Assert that artifacts are signed
  * Configuration: Required signing method, tags requiring signing

* **Container images are signed with cosign/sigstore**: Container images must be signed using cosign or sigstore for supply chain security.
  * Collector(s): Detect cosign signing step in CI; verify signature in registry
  * Component JSON:
    * `.containers.builds[].signed` - Boolean for image signing
    * `.containers.builds[].signature_type` - Signature type
    * `.containers.summary.all_signed` - Boolean for all images signed
  * Policy: Assert that container images are signed
  * Configuration: Required signature type (default: "cosign")

* **Artifact signatures are published to transparency log**: Signatures should be recorded in a transparency log (Rekor) for auditability.
  * Collector(s): Check for transparency log publication in signing process
  * Component JSON:
    * `.artifacts.transparency_log.published` - Boolean for transparency log publication
    * `.artifacts.transparency_log.entry_id` - Log entry identifier
  * Policy: Assert that signatures are published to transparency log
  * Configuration: None

### Artifact Publication

* **Artifacts are published to approved repositories**: Build artifacts must be published to organization-approved artifact repositories.
  * Collector(s): Detect artifact publication in CI; extract target repositories
  * Component JSON:
    * `.artifacts.published` - Boolean for artifact publication
    * `.artifacts.repositories` - Array of repositories used
    * `.artifacts.uses_approved_repositories` - Boolean for approved repos only
  * Policy: Assert that artifacts are published to approved repositories
  * Configuration: Approved artifact repository patterns

* **Package version follows semantic versioning**: Published packages must use semantic versioning for proper dependency resolution.
  * Collector(s): Extract package version from manifest and publication metadata
  * Component JSON:
    * `.artifacts.version` - Published package version
    * `.artifacts.is_semver` - Boolean for semver format
  * Policy: Assert that published packages use semantic versioning
  * Configuration: None

* **Artifact includes provenance attestation**: Artifacts should include SLSA provenance attestation for supply chain security.
  * Collector(s): Check for provenance generation in CI (SLSA generator, cosign attest)
  * Component JSON:
    * `.artifacts.provenance.exists` - Boolean for provenance presence
    * `.artifacts.provenance.type` - Provenance type (slsa-l1, slsa-l2, slsa-l3)
    * `.artifacts.provenance.verified` - Boolean for verified provenance
  * Policy: Assert that artifacts include provenance attestation
  * Configuration: Minimum SLSA level (default: l2)

### SBOM Generation

* **SBOM is generated for builds**: Software Bill of Materials must be generated for all builds.
  * Collector(s): Detect SBOM generation in CI; verify SBOM artifact existence
  * Component JSON:
    * `.sbom.exists` - Boolean for SBOM presence
    * `.sbom.format` - SBOM format (spdx, cyclonedx)
    * `.sbom.tool` - Tool used to generate SBOM
  * Policy: Assert that SBOM is generated
  * Configuration: Required SBOM format

* **SBOM is published alongside artifacts**: Generated SBOM must be published to artifact repository alongside the build artifacts.
  * Collector(s): Verify SBOM publication in artifact repository
  * Component JSON:
    * `.sbom.published` - Boolean for SBOM publication
    * `.sbom.location` - Location of published SBOM
  * Policy: Assert that SBOM is published
  * Configuration: None

* **SBOM is attached to container images**: Container images should have SBOM attached as attestation or alongside in registry.
  * Collector(s): Check for SBOM attestation on container images in registry
  * Component JSON:
    * `.containers.builds[].sbom_attached` - Boolean for SBOM attachment
    * `.containers.builds[].sbom_location` - Location of attached SBOM
  * Policy: Assert that container images have SBOM attached
  * Configuration: None

---

## Local Development Experience

### Local Build and Run

* **Local build instructions exist**: README or CONTRIBUTING must document how to build the project locally.
  * Collector(s): Check README for build instructions section or CONTRIBUTING.md; verify documented commands work
  * Component JSON:
    * `.repo.readme.sections` - Array of README sections
    * `.repo.readme.has_build_instructions` - Boolean for build instructions presence
    * `.repo.build_docs.location` - Location of build documentation
  * Policy: Assert that local build instructions exist
  * Configuration: Expected section headings (e.g., ["Building", "Build", "Development"])

* **Local run instructions exist**: Documentation must explain how to run the service locally.
  * Collector(s): Check README for run/start instructions; verify make run or equivalent exists
  * Component JSON:
    * `.repo.readme.has_run_instructions` - Boolean for run instructions presence
    * `.repo.run_docs.location` - Location of run documentation
  * Policy: Assert that local run instructions exist
  * Configuration: Expected section headings (e.g., ["Running", "Run", "Getting Started"])

* **Standard local development commands work**: make build, make test, make run (or equivalents) should succeed.
  * Collector(s): Execute standard commands in clean environment and verify success (may be periodic/scheduled)
  * Component JSON:
    * `.repo.local_dev.build_works` - Boolean for build success
    * `.repo.local_dev.test_works` - Boolean for test success
    * `.repo.local_dev.run_works` - Boolean for run success
    * `.repo.local_dev.verified_at` - Timestamp of last verification
  * Policy: Assert that standard development commands work
  * Configuration: Commands to verify, verification frequency

### Development Environment Configuration

* **Dev container or codespace configuration exists**: Projects should provide dev container configuration for consistent development environments.
  * Collector(s): Check for .devcontainer/devcontainer.json or .codespaces configuration
  * Component JSON:
    * `.repo.devcontainer.exists` - Boolean for dev container presence
    * `.repo.devcontainer.path` - Path to dev container configuration
    * `.repo.devcontainer.valid` - Boolean for valid configuration
  * Policy: Assert that dev container configuration exists
  * Configuration: None (may be advisory)

* **Docker Compose configuration exists for local development**: Projects with service dependencies should provide docker-compose for local development.
  * Collector(s): Check for docker-compose.yml, docker-compose.dev.yml, or compose.yml
  * Component JSON:
    * `.repo.compose.exists` - Boolean for compose file presence
    * `.repo.compose.path` - Path to compose file
    * `.repo.compose.services` - Array of defined services
  * Policy: Assert that compose configuration exists for services with dependencies
  * Configuration: Tags requiring compose (e.g., ["has-dependencies", "service"])

* **Environment variable template exists**: Projects should provide .env.example or .env.template documenting required variables.
  * Collector(s): Check for environment template files
  * Component JSON:
    * `.repo.env_template.exists` - Boolean for env template presence
    * `.repo.env_template.path` - Path to template file
    * `.repo.env_template.variables` - Array of documented variables
  * Policy: Assert that environment template exists
  * Configuration: None

---

## Summary Policies

* **Build and CI compliance score**: Aggregate score reflecting overall build and CI quality.
  * Collector(s): Calculate composite score from all build/CI policy results
  * Component JSON:
    * `.build.compliance_score` - Numeric score (0-100)
    * `.build.compliance_factors` - Array of contributing factors
  * Policy: Assert that build compliance score meets minimum threshold
  * Configuration: Minimum score (default: 70), factor weights

* **All required build steps are configured**: Meta-check that all applicable build guardrails are satisfied.
  * Collector(s): Aggregate results from build-related policy checks
  * Component JSON:
    * `.build.compliance.passing_checks` - Number of passing checks
    * `.build.compliance.total_checks` - Total applicable checks
    * `.build.compliance.percentage` - Compliance percentage
  * Policy: Assert that build compliance percentage meets threshold
  * Configuration: Minimum compliance percentage (default: 90%)

* **Golden path alignment score**: Measure of how closely project follows organizational golden paths.
  * Collector(s): Aggregate golden path policy results
  * Component JSON:
    * `.repo.golden_path.alignment_score` - Alignment score (0-100)
    * `.repo.golden_path.deviations` - Array of deviations from golden path
  * Policy: Assert that golden path alignment meets threshold
  * Configuration: Minimum alignment score, critical deviations that fail regardless
