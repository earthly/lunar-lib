# Component JSON Structure

This document defines the standard structure for each top-level category in the Component JSON—with examples and key policy paths.

**See also:** [conventions.md](conventions.md) for design principles, source metadata patterns, presence detection, and other conventions.

---

## Key Paths Quick Reference

This table lists important sub-objects within each category. For full details, see the category sections linked below.

| Path | Description |
|------|-------------|
| **[`.repo`](cat-repo.md)** | **Repository structure, README, standard files** |
| `.repo.readme` | README file info (`exists`, `path`, `lines`, `sections`) |
| `.repo.files` | Standard file presence booleans (`gitignore`, `license`, `makefile`, etc.) |
| `.repo.license` | License info (`type`, `path`) |
| `.repo.languages` | Detected languages (`primary`, `all`) |
| **[`.ownership`](cat-ownership.md)** | **Code ownership, maintainers, team info** |
| `.ownership.codeowners` | CODEOWNERS info (`exists`, `valid`, `path`, `owners`, `rules`) |
| `.ownership.codeowners.rules[]` | Parsed rules (`pattern`, `owners`, `owner_count`, `line`) |
| `.ownership.codeowners.team_owners` | Team owners (`@org/team`) |
| `.ownership.codeowners.individual_owners` | Individual owners (`@user`, `email`) |
| `.ownership.maintainers` | List of maintainer emails |
| **[`.catalog`](cat-catalog.md)** | **Service catalog entries (Backstage, etc.)** |
| `.catalog.entity` | Entity metadata (`name`, `type`, `owner`, `lifecycle`, `tags`) |
| `.catalog.annotations` | Service annotations (`pagerduty_service`, `grafana_dashboard`, `runbook`) |
| `.catalog.apis` | API relationships (`provides`, `consumes`) |
| **[`.vcs`](cat-vcs.md)** | **Version control settings (branch protection, etc.)** |
| `.vcs.branch_protection` | Protection settings (`enabled`, `required_approvals`, `require_codeowner_review`) |
| `.vcs.pr` | PR-specific data (only in PR context) — see [PR-Specific Data](conventions.md#pr-specific-data) |
| `.vcs.pr.ticket` | Extracted ticket reference (`id`, `source`, `url`) |
| **[`.containers`](cat-containers.md)** | **Container images, Dockerfiles, registries** |
| `.containers.definitions[]` | Dockerfile definitions (`path`, `valid`, `base_images`, `final_stage`, `labels`) |
| `.containers.definitions[].base_images[]` | Base image info (`reference`, `image`, `tag`) |
| `.containers.definitions[].final_stage` | Final stage info (`base_name`, `base_image`, `user`, `has_healthcheck`) |
| `.containers.builds[]` | Built images (`image`, `tag`, `signed`, `has_git_sha_label`) |
| **[`.k8s`](cat-k8s.md)** | **Kubernetes manifests and configuration** |
| `.k8s.manifests[]` | Manifest files (`path`, `valid`, `resources`) |
| `.k8s.workloads[]` | Workload resources (`kind`, `name`, `replicas`, `containers`) |
| `.k8s.workloads[].containers[]` | Container specs (`has_resources`, `has_liveness_probe`, `runs_as_non_root`) |
| `.k8s.pdbs[]` | PodDisruptionBudgets (`name`, `target_workload`, `min_available`) |
| `.k8s.hpas[]` | HorizontalPodAutoscalers (`min_replicas`, `max_replicas`) |
| `.k8s.summary` | Aggregated checks (`all_have_resources`, `all_have_probes`, `all_have_pdb`) |
| **[`.iac`](cat-iac.md)** | **Infrastructure as Code (Terraform, Pulumi, etc.)** |
| `.iac.source` | Tool metadata (`tool`, `version`) |
| `.iac.files[]` | IaC files (`path`, `valid`, `error?`) |
| `.iac.modules[]` | IaC modules (`path`, `resources[]`, `analysis`) |
| `.iac.modules[].resources[]` | Normalized resources (`type`, `name`, `category`, `has_prevent_destroy`) |
| `.iac.modules[].analysis` | Per-module analysis (`internet_accessible`, `has_waf`) |
| `.iac.native.terraform.files[]` | Full parsed HCL per file (`path`, `hcl`) — for terraform-specific policy |
| **[`.ci`](cat-ci.md)** | **CI/CD pipeline execution and configuration** |
| `.ci.run` | Current run info (`id`, `status`, `duration_seconds`) |
| `.ci.jobs[]` | Job details (`name`, `status`, `duration_seconds`) |
| `.ci.steps_executed` | Step booleans (`lint`, `build`, `unit_test`, `security_scan`) |
| `.ci.artifacts` | Build artifacts (`images_pushed`, `sbom_generated`) |
| **[`.testing`](cat-testing.md)** | **Test execution results and code coverage** |
| `.testing.results` | Test results (`total`, `passed`, `failed`, `skipped`) |
| `.testing.failures[]` | Failure details (`name`, `file`, `line`, `message`) |
| `.testing.coverage` | Coverage data (`percentage`, `lines`, `files[]`) |
| `.testing.coverage.lines` | Line coverage (`covered`, `total`) |
| **[`.sca`](cat-sca.md)** | **Software Composition Analysis (dependency vulnerabilities)** |
| `.sca.source` | Tool source (`tool`, `version`, `integration`) |
| `.sca.vulnerabilities` | Vuln counts (`critical`, `high`, `medium`, `low`, `total`) |
| `.sca.findings[]` | Detailed findings (`severity`, `package`, `cve`, `fix_version`, `fixable`) |
| `.sca.summary` | Summary booleans (`has_critical`, `has_high`, `all_fixable`) |
| **[`.sast`](cat-sast.md)** | **Static Application Security Testing** |
| `.sast.findings` | Finding counts by severity |
| `.sast.issues[]` | Issue details (`severity`, `rule`, `file`, `line`, `message`) |
| **[`.secrets`](cat-secrets.md)** | **Secret/credential scanning** |
| `.secrets.findings` | Finding counts (`total`) |
| `.secrets.clean` | Boolean — no secrets detected |
| **[`.container_scan`](cat-container-scan.md)** | **Container image vulnerability scanning** |
| `.container_scan.vulnerabilities` | Vuln counts by severity |
| `.container_scan.summary` | Summary booleans (`has_critical`, `has_high`) |
| **[`.observability`](cat-observability.md)** | **Monitoring, logging, tracing configuration** |
| `.observability.logging` | Logging config (`configured`, `structured`) |
| `.observability.metrics` | Metrics config (`configured`, `endpoint`, `golden_signals`) |
| `.observability.metrics.golden_signals` | Four signals (`latency`, `traffic`, `errors`, `saturation`) |
| `.observability.dashboard` | Dashboard info (`exists`, `url`) |
| `.observability.alerts` | Alert config (`configured`, `count`) |
| `.observability.summary` | Aggregated checks (`golden_signals_complete`, `has_dashboard`) |
| **[`.oncall`](cat-oncall.md)** | **On-call, incident management, runbooks** |
| `.oncall.schedule` | Schedule info (`exists`, `participants`, `rotation`) |
| `.oncall.escalation` | Escalation info (`exists`, `levels`) |
| `.oncall.runbook` | Runbook info (`exists`, `path`, `url`) |
| `.oncall.sla` | SLA info (`defined`, `response_minutes`, `uptime_percentage`) |
| `.oncall.disaster_recovery.plan` | DR plan info (`exists`, `path`, `rto_minutes`, `rpo_minutes`, `last_reviewed`) |
| `.oncall.disaster_recovery.exercises[]` | DR exercise records (`date`, `path`, `exercise_type`, `sections`) |
| `.oncall.disaster_recovery.latest_exercise_date` | Date of most recent exercise |
| `.oncall.disaster_recovery.exercise_count` | Total number of exercise records |
| **[`.compliance`](cat-compliance.md)** | **Compliance regime data** |
| `.compliance.regimes` | List of applicable regimes (e.g., `["soc2", "pci-dss"]`) |
| `.compliance.data_classification` | Data classification (`level`, `contains_pii`, `contains_pci`) |
| `.compliance.controls` | Control status (`access_reviews`, `audit_logging`, `encryption_at_rest`) |
| **[`.api`](cat-api.md)** | **API specifications and documentation** |
| `.api.specs[]` | API spec files (`type`, `path`, `valid`, `version`) |
| **[`.code_patterns`](cat-code-patterns.md)** | **AST-based code pattern analysis (Strategy 16)** |
| `.code_patterns.source` | Tool source (`tool`, `version`) |
| `.code_patterns.security` | Security anti-patterns (`sql_concat`, `eval_exec`, `weak_crypto`, etc.) |
| `.code_patterns.logging` | Logging patterns (`printf_violations`, `uses_structured_logging`) |
| `.code_patterns.errors` | Error handling (`ignored_errors`, `unwrapped_errors`, `panic_usage`) |
| `.code_patterns.http` | HTTP client patterns (`missing_timeout`, `default_client_usage`) |
| `.code_patterns.resources` | Resource management (`missing_close`) |
| `.code_patterns.concurrency` | Concurrency patterns (`missing_unlock`) |
| `.code_patterns.deprecated` | Deprecated API usage (`api_usage`) |
| `.code_patterns.metrics` | Declared metrics (`declared[]`, `count`, `naming_violations`) |
| `.code_patterns.tracing` | Tracing impl (`spans_created`, `propagation`) |
| `.code_patterns.lifecycle` | Lifecycle patterns (`sigterm_handled`, `graceful_shutdown`) |
| `.code_patterns.feature_flags` | Feature flag inventory (`flags[]`, `count`, `library`) |
| `.code_patterns.health` | Health check impl (`endpoint_implemented`, `dependency_checks`) |
| `.code_patterns.config` | Config patterns (`env_vars[]`, `missing_defaults`) |
| `.code_patterns.testing` | Test quality (`tests_without_assertions`, `empty_catch_blocks`) |
| **[`.ai_use`](cat-ai-use.md)** | **AI coding assistant usage (instruction files, CI tools, authorship)** |
| `.ai_use.instructions.root` | Root instruction file info (`exists`, `filename`, `lines`, `bytes`, `sections[]`) |
| `.ai_use.instructions.all[]` | All instruction files (`path`, `dir`, `filename`, `lines`, `bytes`, `sections[]`, `is_symlink`) |
| `.ai_use.instructions.count` | Total instruction files found |
| `.ai_use.instructions.total_bytes` | Combined size of non-symlink files (context window budget) |
| `.ai_use.instructions.directories[]` | Per-directory view (`dir`, `files[]` with symlink status) |
| `.ai_use.plans_dir` | Plans directory info (`exists`, `path`, `file_count`) |
| `.ai_use.cicd.cmds[]` | AI CLI invocations in CI (`cmd`, `tool`, `version`, plus tool-specific config flags) |
| `.ai_use.authorship` | AI authorship annotations (`provider`, `total_commits`, `annotated_commits`) |
| `.ai_use.authorship.git_ai` | Git AI notes data (`notes_ref_exists`, `commits_with_notes`) |
| `.ai_use.authorship.trailers` | Git trailer data (per-commit `sha`, `model`, `tokens`, `has_annotation`) |
| **`.lang.<language>`** | **Language-specific data (Go, Rust, Java, etc.)** — see [Language-Specific Data](conventions.md#language-specific-data) |
| `.lang.<language>.version` | Language/runtime version (e.g., `"17"` for Java, `"1.21"` for Go) |
| `.lang.<language>.build_systems` | Build tools array (`["maven"]`, `["gradle", "maven"]`, `["go"]`) |
| `.lang.<language>.dependencies` | Full dependency data (`direct[]`, `transitive[]`) |
| `.lang.<language>.native.<tool>` | Build-system specific data (e.g., `.lang.java.native.gradle`) |
| `.lang.go.module` | Go module path |
| `.lang.go.golangci_lint` | golangci-lint findings |
| `.lang.go.context` | Context propagation (`wrong_position`, `background_misuse`) |
| `.lang.go.init` | Init function patterns (`side_effects`) |
| `.lang.java.group_id` | Maven/Gradle group ID |
| `.lang.java.artifact_id` | Maven/Gradle artifact ID |
| `.lang.java.spotbugs` | SpotBugs findings by severity |
| `.lang.rust.unsafe_blocks` | Unsafe block count/locations |
| `.lang.rust.edition` | Rust edition (`2021`, `2024`) |

---

## Category Documentation

Each category has its own detailed documentation:

- [`.repo`](cat-repo.md) — Repository structure, README, standard files
- [`.ownership`](cat-ownership.md) — Code ownership, maintainers, team info
- [`.catalog`](cat-catalog.md) — Service catalog entries (Backstage, etc.)
- [`.vcs`](cat-vcs.md) — Version control settings (branch protection, etc.)
- [`.containers`](cat-containers.md) — Container images, Dockerfiles, registries
- [`.k8s`](cat-k8s.md) — Kubernetes manifests and configuration
- [`.iac`](cat-iac.md) — Infrastructure as Code (Terraform, Pulumi, etc.)
- [`.ci`](cat-ci.md) — CI/CD pipeline execution and configuration
- [`.testing`](cat-testing.md) — Test execution results and code coverage
- [`.sca`](cat-sca.md) — Software Composition Analysis (dependency vulnerabilities)
- [`.sast`](cat-sast.md) — Static Application Security Testing
- [`.secrets`](cat-secrets.md) — Secret/credential scanning
- [`.container_scan`](cat-container-scan.md) — Container image vulnerability scanning
- [`.observability`](cat-observability.md) — Monitoring, logging, tracing configuration
- [`.oncall`](cat-oncall.md) — On-call, incident management, runbooks
- [`.compliance`](cat-compliance.md) — Compliance regime data
- [`.api`](cat-api.md) — API specifications and documentation
- [`.code_patterns`](cat-code-patterns.md) — AST-based code pattern analysis
- [`.ai_use`](cat-ai-use.md) — AI coding assistant usage (instruction files, CI tools, authorship)

