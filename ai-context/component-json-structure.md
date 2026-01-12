# Component JSON Structure

This document defines the standard structure for each top-level category in the Component JSON—with examples and key policy paths.

**See also:** [component-json-conventions.md](component-json-conventions.md) for design principles, source metadata patterns, presence detection, and other conventions.

---

## Key Paths Quick Reference

This table lists important sub-objects within each category. For full details, see the category sections below.

| Path | Description |
|------|-------------|
| **`.repo`** | **Repository structure, README, standard files** |
| `.repo.readme` | README file info (`exists`, `path`, `lines`, `sections`) |
| `.repo.files` | Standard file presence booleans (`gitignore`, `license`, `makefile`, etc.) |
| `.repo.license` | License info (`type`, `path`) |
| `.repo.languages` | Detected languages (`primary`, `all`) |
| **`.ownership`** | **Code ownership, maintainers, team info** |
| `.ownership.codeowners` | CODEOWNERS info (`exists`, `valid`, `has_default_rule`, `owners`) |
| `.ownership.maintainers` | List of maintainer emails |
| **`.catalog`** | **Service catalog entries (Backstage, etc.)** |
| `.catalog.entity` | Entity metadata (`name`, `type`, `owner`, `lifecycle`, `tags`) |
| `.catalog.annotations` | Service annotations (`pagerduty_service`, `grafana_dashboard`, `runbook`) |
| `.catalog.apis` | API relationships (`provides`, `consumes`) |
| **`.vcs`** | **Version control settings (branch protection, etc.)** |
| `.vcs.branch_protection` | Protection settings (`enabled`, `required_approvals`, `require_codeowner_review`) |
| `.vcs.pr` | PR-specific data (only in PR context) — see [PR-Specific Data](component-json-conventions.md#pr-specific-data) |
| `.vcs.pr.ticket` | Extracted ticket reference (`id`, `source`, `url`) |
| **`.containers`** | **Container images, Dockerfiles, registries** |
| `.containers.definitions[]` | Dockerfile definitions (`path`, `valid`, `base_images`, `final_stage`, `labels`) |
| `.containers.definitions[].base_images[]` | Base image info (`reference`, `image`, `tag`) |
| `.containers.definitions[].final_stage` | Final stage info (`base_name`, `base_image`, `user`, `has_healthcheck`) |
| `.containers.builds[]` | Built images (`image`, `tag`, `signed`, `has_git_sha_label`) |
| **`.k8s`** | **Kubernetes manifests and configuration** |
| `.k8s.manifests[]` | Manifest files (`path`, `valid`, `resources`) |
| `.k8s.workloads[]` | Workload resources (`kind`, `name`, `replicas`, `containers`) |
| `.k8s.workloads[].containers[]` | Container specs (`has_resources`, `has_liveness_probe`, `runs_as_non_root`) |
| `.k8s.pdbs[]` | PodDisruptionBudgets (`name`, `target_workload`, `min_available`) |
| `.k8s.hpas[]` | HorizontalPodAutoscalers (`min_replicas`, `max_replicas`) |
| `.k8s.summary` | Aggregated checks (`all_have_resources`, `all_have_probes`, `all_have_pdb`) |
| **`.iac`** | **Infrastructure as Code (Terraform, Pulumi, etc.)** |
| `.iac.files[]` | IaC files (`path`, `valid`) |
| `.iac.resources[]` | Resources (`type`, `provider`, `resource_type`, `encrypted`, `deletion_protected`) |
| `.iac.analysis` | Analysis results (`has_backend`, `internet_accessible`, `has_waf`) |
| `.iac.datastores` | Datastore summary (`count`, `all_deletion_protected`, `all_encrypted`) |
| `.iac.summary` | Aggregated checks (`all_valid`, `resource_count`) |
| **`.ci`** | **CI/CD pipeline execution and configuration** |
| `.ci.run` | Current run info (`id`, `status`, `duration_seconds`) |
| `.ci.jobs[]` | Job details (`name`, `status`, `duration_seconds`) |
| `.ci.steps_executed` | Step booleans (`lint`, `build`, `unit_test`, `security_scan`) |
| `.ci.artifacts` | Build artifacts (`images_pushed`, `sbom_generated`) |
| **`.testing`** | **Test execution results and code coverage** |
| `.testing.results` | Test results (`total`, `passed`, `failed`, `skipped`) |
| `.testing.failures[]` | Failure details (`name`, `file`, `line`, `message`) |
| `.testing.coverage` | Coverage data (`percentage`, `meets_threshold`, `threshold`) |
| `.testing.coverage.lines` | Line coverage (`covered`, `total`) |
| **`.sca`** | **Software Composition Analysis (dependency vulnerabilities)** |
| `.sca.source` | Tool source (`tool`, `version`, `integration`) |
| `.sca.vulnerabilities` | Vuln counts (`critical`, `high`, `medium`, `low`, `total`) |
| `.sca.findings[]` | Detailed findings (`severity`, `package`, `cve`, `fix_version`, `fixable`) |
| `.sca.summary` | Summary booleans (`has_critical`, `has_high`, `all_fixable`) |
| **`.sast`** | **Static Application Security Testing** |
| `.sast.findings` | Finding counts by severity |
| `.sast.issues[]` | Issue details (`severity`, `rule`, `file`, `line`, `message`) |
| **`.secrets`** | **Secret/credential scanning** |
| `.secrets.findings` | Finding counts (`total`) |
| `.secrets.clean` | Boolean — no secrets detected |
| **`.container_scan`** | **Container image vulnerability scanning** |
| `.container_scan.vulnerabilities` | Vuln counts by severity |
| `.container_scan.summary` | Summary booleans (`has_critical`, `has_high`) |
| **`.observability`** | **Monitoring, logging, tracing configuration** |
| `.observability.logging` | Logging config (`configured`, `structured`) |
| `.observability.metrics` | Metrics config (`configured`, `endpoint`, `golden_signals`) |
| `.observability.metrics.golden_signals` | Four signals (`latency`, `traffic`, `errors`, `saturation`) |
| `.observability.dashboard` | Dashboard info (`exists`, `url`) |
| `.observability.alerts` | Alert config (`configured`, `count`) |
| `.observability.summary` | Aggregated checks (`golden_signals_complete`, `has_dashboard`) |
| **`.oncall`** | **On-call, incident management, runbooks** |
| `.oncall.schedule` | Schedule info (`exists`, `participants`, `rotation`) |
| `.oncall.escalation` | Escalation info (`exists`, `levels`) |
| `.oncall.runbook` | Runbook info (`exists`, `path`, `url`) |
| `.oncall.sla` | SLA info (`defined`, `response_minutes`, `uptime_percentage`) |
| **`.compliance`** | **Compliance regime data** |
| `.compliance.regimes` | List of applicable regimes (e.g., `["soc2", "pci-dss"]`) |
| `.compliance.data_classification` | Data classification (`level`, `contains_pii`, `contains_pci`) |
| `.compliance.controls` | Control status (`access_reviews`, `audit_logging`, `encryption_at_rest`) |
| **`.api`** | **API specifications and documentation** |
| `.api.specs[]` | API spec files (`type`, `path`, `valid`, `version`) |
| **`.lang.<language>`** | **Language-specific data (Go, Rust, Java, etc.)** — see [Language-Specific Data](component-json-conventions.md#language-specific-data) |
| `.lang.<language>.version` | Language/runtime version (e.g., `"17"` for Java, `"1.21"` for Go) |
| `.lang.<language>.build_system` | Build tool name (`maven`, `gradle`, `cargo`, etc.) |
| `.lang.<language>.dependencies` | Dependency counts (`direct`, `transitive`) |
| `.lang.<language>.native.<tool>` | Build-system specific data (e.g., `.lang.java.native.gradle`) |
| `.lang.go.module` | Go module path |
| `.lang.go.golangci_lint` | golangci-lint findings |
| `.lang.java.group_id` | Maven/Gradle group ID |
| `.lang.java.artifact_id` | Maven/Gradle artifact ID |
| `.lang.java.spotbugs` | SpotBugs findings by severity |
| `.lang.rust.unsafe_blocks` | Unsafe block count/locations |
| `.lang.rust.edition` | Rust edition (`2021`, `2024`) |

---

## Category: `.repo`

Repository structure, README, and standard files.

```json
{
  "repo": {
    "readme": {
      "exists": true,
      "path": "README.md",
      "lines": 150,
      "sections": ["Installation", "Usage", "API", "Contributing"]
    },
    "files": {
      "gitignore": true,
      "dockerignore": true,
      "editorconfig": false,
      "license": true,
      "contributing": true,
      "makefile": true
    },
    "license": {
      "type": "MIT",
      "path": "LICENSE"
    },
    "languages": {
      "primary": "go",
      "all": ["go", "python", "shell"]
    }
  }
}
```

**Key policy paths:**
- `.repo.readme.exists` — README present
- `.repo.readme.path` — Which README file was found
- `.repo.readme.sections` — Section headings for content requirements
- `.repo.files.<name>` — Standard file presence
- `.repo.languages.primary` — Primary language detection

---

## Category: `.ownership`

Code ownership and team information.

```json
{
  "ownership": {
    "codeowners": {
      "exists": true,
      "valid": true,
      "path": "CODEOWNERS",
      "errors": [],
      "has_default_rule": true,
      "owners": ["@org/platform-team", "@jdoe"]
    },
    "maintainers": ["alice@example.com", "bob@example.com"]
  }
}
```

**Key policy paths:**
- `.ownership.codeowners.exists` — CODEOWNERS file present
- `.ownership.codeowners.valid` — Syntax valid
- `.ownership.codeowners.has_default_rule` — Has catch-all rule

---

## Category: `.catalog`

Service catalog entries. Tool-agnostic structure that works with Backstage, ServiceNow, or custom catalogs.

```json
{
  "catalog": {
    "exists": true,
    "source": {
      "tool": "backstage",
      "file": "catalog-info.yaml"
    },
    "entity": {
      "name": "payment-api",
      "type": "service",
      "description": "Payment processing API",
      "owner": "team-payments",
      "system": "payment-platform",
      "lifecycle": "production",
      "tags": ["payments", "api", "tier1"]
    },
    "annotations": {
      "pagerduty_service": "PXXXXXX",
      "grafana_dashboard": "https://...",
      "runbook": "https://...",
      "slack_channel": "#payments-oncall"
    },
    "apis": {
      "provides": ["payment-api"],
      "consumes": ["user-api", "notification-api"]
    },
    "dependencies": ["database-payments", "cache-redis"]
  }
}
```

**Key policy paths:**
- `.catalog.exists` — Service catalog entry present
- `.catalog.entity.owner` — Owner defined
- `.catalog.entity.lifecycle` — Lifecycle stage
- `.catalog.annotations.pagerduty_service` — PagerDuty linked
- `.catalog.annotations.grafana_dashboard` — Dashboard linked

---

## Category: `.vcs`

Version control settings (GitHub, GitLab, Bitbucket, etc.).

```json
{
  "vcs": {
    "provider": "github",
    "default_branch": "main",
    "branch_protection": {
      "enabled": true,
      "branch": "main",
      "require_pr": true,
      "required_approvals": 2,
      "require_codeowner_review": true,
      "require_status_checks": true,
      "required_checks": ["ci/build", "ci/test"],
      "allow_force_push": false
    },
    "pr": {
      "number": 123,
      "title": "[ABC-456] Add payment validation",
      "description": "This PR adds validation logic for payment amounts...",
      "author": "jdoe",
      "labels": ["enhancement", "payments"],
      "reviewers": ["alice", "bob"],
      "approved": true,
      "commits": 3,
      "files_changed": 12,
      "ticket": {
        "id": "ABC-456",
        "source": "jira",
        "url": "https://acme.atlassian.net/browse/ABC-456"
      }
    }
  }
}
```

**Note:** The `.vcs.pr` object is only present when in PR context. Check `c.exists(".vcs.pr")` before accessing.

**Key policy paths:**
- `.vcs.default_branch` — Default branch name
- `.vcs.branch_protection.enabled` — Protection active
- `.vcs.branch_protection.required_approvals` — Min approvals
- `.vcs.branch_protection.require_codeowner_review` — CODEOWNER approval
- `.vcs.pr.ticket.id` — Extracted ticket reference (only in PR context)
- `.vcs.pr.approved` — PR has required approvals (only in PR context)

---

## Category: `.containers`

Container images and Dockerfiles. Tool-agnostic (works with Docker, Podman, Buildah, etc.).

```json
{
  "containers": {
    "definitions": [
      {
        "path": "Dockerfile",
        "valid": true,
        "base_images": [
          {
            "reference": "golang:1.21-alpine",
            "image": "golang",
            "tag": "1.21-alpine"
          },
          {
            "reference": "gcr.io/distroless/static-debian12:nonroot-amd64",
            "image": "gcr.io/distroless/static-debian12",
            "tag": "nonroot-amd64"
          }
        ],
        "final_stage": {
          "base_name": "runtime",
          "base_image": "gcr.io/distroless/static-debian12:nonroot-amd64",
          "user": "nonroot",
          "has_healthcheck": false
        },
        "labels": {
          "org.opencontainers.image.source": "https://github.com/acme/api"
        }
      }
    ],
    "builds": [
      {
        "image": "gcr.io/acme/payment-api:v1.2.3",
        "registry": "gcr.io",
        "tag": "v1.2.3",
        "has_git_sha_label": true,
        "signed": true
      }
    ],
    "registries_used": ["docker.io", "gcr.io"]
  }
}
```

**Key policy paths:**
- `.containers.definitions[].valid` — Dockerfile valid
- `.containers.definitions[].final_stage.user` — User instruction value
- `.containers.definitions[].base_images[].tag` — Tag value (check for `null` or `"latest"`)
- `.containers.builds[].signed` — Image signed
- `.containers.registries_used` — Registries for allowlist checking

---

## Category: `.k8s`

Kubernetes manifests. This is specific enough to warrant its own category.

```json
{
  "k8s": {
    "manifests": [
      {
        "path": "deploy/deployment.yaml",
        "valid": true,
        "error": null,
        "resources": [
          {
            "kind": "Deployment",
            "name": "payment-api",
            "namespace": "payments"
          }
        ]
      }
    ],
    "workloads": [
      {
        "kind": "Deployment",
        "name": "payment-api",
        "namespace": "payments",
        "path": "deploy/deployment.yaml",
        "replicas": 3,
        "containers": [
          {
            "name": "api",
            "image": "gcr.io/acme/payment-api:v1.2.3",
            "has_resources": true,
            "has_requests": true,
            "has_limits": true,
            "cpu_request": "100m",
            "cpu_limit": "500m",
            "memory_request": "128Mi",
            "memory_limit": "512Mi",
            "has_liveness_probe": true,
            "has_readiness_probe": true,
            "runs_as_non_root": true,
            "read_only_root_fs": true,
            "privileged": false
          }
        ]
      }
    ],
    "pdbs": [
      {
        "name": "payment-api-pdb",
        "namespace": "payments",
        "path": "deploy/pdb.yaml",
        "target_workload": "payment-api",
        "min_available": 2
      }
    ],
    "hpas": [
      {
        "name": "payment-api-hpa",
        "namespace": "payments",
        "path": "deploy/hpa.yaml",
        "target_workload": "payment-api",
        "min_replicas": 3,
        "max_replicas": 10
      }
    ],
    "summary": {
      "all_valid": true,
      "all_have_resources": true,
      "all_have_probes": true,
      "all_non_root": true,
      "all_have_pdb": true
    }
  }
}
```

**Key policy paths:**
- `.k8s.manifests[].valid` — Manifest parses
- `.k8s.workloads[].containers[].has_resources` — Resource limits set
- `.k8s.workloads[].containers[].runs_as_non_root` — Security context
- `.k8s.hpas[].min_replicas` — HPA minimum
- `.k8s.summary.all_have_pdb` — All workloads have PDB

---

## Category: `.iac`

Infrastructure as Code. Normalized across Terraform, Pulumi, CloudFormation, etc.

```json
{
  "iac": {
    "tool": "terraform",
    "files": [
      {
        "path": "infrastructure/main.tf",
        "valid": true
      }
    ],
    "resources": [
      {
        "type": "database",
        "provider": "aws",
        "resource_type": "aws_db_instance",
        "name": "payments_db",
        "path": "infrastructure/database.tf",
        "deletion_protected": true,
        "encrypted": true,
        "backup_enabled": true,
        "multi_az": true
      },
      {
        "type": "storage",
        "provider": "aws",
        "resource_type": "aws_s3_bucket",
        "name": "payment_logs",
        "path": "infrastructure/storage.tf",
        "deletion_protected": true,
        "versioning_enabled": true,
        "encrypted": true
      },
      {
        "type": "load_balancer",
        "provider": "aws",
        "resource_type": "aws_alb",
        "name": "api_lb",
        "path": "infrastructure/network.tf",
        "internet_facing": true,
        "waf_enabled": true,
        "ssl_policy": "ELBSecurityPolicy-TLS-1-2-2017-01"
      }
    ],
    "analysis": {
      "has_backend": true,
      "versions_pinned": true,
      "internet_accessible": true,
      "has_waf": true
    },
    "datastores": {
      "count": 2,
      "all_deletion_protected": true,
      "all_encrypted": true,
      "unprotected": []
    },
    "summary": {
      "all_valid": true,
      "resource_count": 15
    }
  }
}
```

**Key policy paths:**
- `.iac.files[].valid` — Config files valid
- `.iac.analysis.internet_accessible` — Public resources
- `.iac.analysis.has_waf` — WAF configured
- `.iac.datastores.all_deletion_protected` — Delete protection
- `.iac.datastores.all_encrypted` — Encryption at rest
- `.iac.resources[].type` — Normalized resource type for queries

---

## Category: `.ci`

CI/CD pipeline data.

```json
{
  "ci": {
    "platform": "github-actions",
    "run": {
      "id": "12345",
      "status": "success",
      "duration_seconds": 342
    },
    "jobs": [
      {"name": "build", "status": "success", "duration_seconds": 120},
      {"name": "test", "status": "success", "duration_seconds": 180}
    ],
    "steps_executed": {
      "lint": true,
      "build": true,
      "unit_test": true,
      "integration_test": true,
      "security_scan": true,
      "deploy": false
    },
    "artifacts": {
      "images_pushed": ["gcr.io/acme/payment-api:v1.2.3"],
      "packages_published": [],
      "sbom_generated": true
    },
    "performance": {
      "avg_duration_seconds": 350
    }
  }
}
```

**Key policy paths:**
- `.ci.run.status` — Current run status
- `.ci.steps_executed.<step>` — Specific step ran
- `.ci.artifacts.sbom_generated` — SBOM created
- `.ci.performance.avg_duration_seconds` — CI speed

---

## Category: `.testing`

Test execution results and code coverage. Normalized across frameworks and tools.

```json
{
  "testing": {
    "source": {
      "framework": "go test",
      "integration": "ci"
    },
    "results": {
      "total": 156,
      "passed": 154,
      "failed": 2,
      "skipped": 0
    },
    "failures": [
      {
        "name": "TestPaymentValidation",
        "file": "payment_test.go",
        "line": 42,
        "message": "expected 200, got 400"
      }
    ],
    "all_passing": false,
    "coverage": {
      "source": {
        "tool": "go cover",
        "integration": "ci"
      },
      "percentage": 85.5,
      "lines": {
        "covered": 1200,
        "total": 1404
      },
      "meets_threshold": true,
      "threshold": 80,
      "files": [
        {
          "path": "payment.go",
          "percentage": 92.0
        }
      ]
    }
  }
}
```

**Key policy paths:**
- `.testing` — Tests executed (use `assert_exists(".testing")`)
- `.testing.results.failed` — Failure count
- `.testing.all_passing` — Clean test run
- `.testing.coverage` — Coverage collected (use `assert_exists(".testing.coverage")`)
- `.testing.coverage.percentage` — Overall coverage
- `.testing.coverage.meets_threshold` — Above minimum

---

## Category: `.sca`

Software Composition Analysis (dependency vulnerabilities). **Normalized across Snyk, Dependabot, Semgrep, Grype, etc.**

```json
{
  "sca": {
    "source": {
      "tool": "snyk",
      "version": "1.1200.0",
      "integration": "github_app"
    },
    "vulnerabilities": {
      "critical": 0,
      "high": 1,
      "medium": 3,
      "low": 8,
      "total": 12
    },
    "findings": [
      {
        "severity": "high",
        "package": "lodash",
        "version": "4.17.19",
        "ecosystem": "npm",
        "cve": "CVE-2021-23337",
        "title": "Prototype Pollution",
        "fix_version": "4.17.21",
        "fixable": true
      }
    ],
    "summary": {
      "has_critical": false,
      "has_high": true,
      "all_fixable": true
    }
  }
}
```

**Key policy paths:**
- `.sca` — SCA scan executed (use `assert_exists(".sca")`)
- `.sca.vulnerabilities.critical` — Critical count
- `.sca.summary.has_critical` — Any criticals
- `.sca.source.tool` — Which tool (if compliance requires specific tool)

**Note:** Policies should use `assert_exists(".sca")` to verify the scanner ran, then check `.sca.vulnerabilities`. Don't check `.sca.source.tool` unless compliance mandates a specific scanner.

---

## Category: `.sast`

Static Application Security Testing. **Normalized across Semgrep, SonarQube, CodeQL, etc.**

```json
{
  "sast": {
    "source": {
      "tool": "semgrep",
      "version": "1.50.0",
      "integration": "ci"
    },
    "findings": {
      "critical": 0,
      "high": 2,
      "medium": 5,
      "low": 12,
      "total": 19
    },
    "issues": [
      {
        "severity": "high",
        "rule": "use-of-weak-crypto",
        "file": "crypto/hash.go",
        "line": 42,
        "message": "Use of weak cryptographic algorithm MD5",
        "category": "security"
      }
    ],
    "summary": {
      "has_critical": false,
      "has_high": true
    }
  }
}
```

**Key policy paths:**
- `.sast` — SAST scan executed (use `assert_exists(".sast")`)
- `.sast.findings.critical` — Critical findings
- `.sast.summary.has_critical` — Any criticals

---

## Category: `.secrets`

Secret/credential scanning. **Normalized across Gitleaks, TruffleHog, detect-secrets, etc.**

```json
{
  "secrets": {
    "source": {
      "tool": "gitleaks",
      "version": "8.18.0",
      "integration": "ci"
    },
    "findings": {
      "total": 0
    },
    "issues": [],
    "clean": true
  }
}
```

**Key policy paths:**
- `.secrets` — Secret scan executed (use `assert_exists(".secrets")`)
- `.secrets.findings.total` — Secrets found
- `.secrets.clean` — No secrets detected

---

## Category: `.container_scan`

Container image vulnerability scanning. **Normalized across Trivy, Grype, Clair, etc.**

```json
{
  "container_scan": {
    "source": {
      "tool": "trivy",
      "version": "0.48.0",
      "integration": "ci"
    },
    "image": "gcr.io/acme/payment-api:v1.2.3",
    "vulnerabilities": {
      "critical": 0,
      "high": 0,
      "medium": 2,
      "low": 5,
      "total": 7
    },
    "os": {
      "family": "alpine",
      "version": "3.19"
    },
    "summary": {
      "has_critical": false,
      "has_high": false
    }
  }
}
```

**Key policy paths:**
- `.container_scan` — Scan executed (use `assert_exists(".container_scan")`)
- `.container_scan.vulnerabilities.critical` — Critical vulns
- `.container_scan.summary.has_critical` — Any criticals

---

## Category: `.observability`

Monitoring, logging, tracing configuration.

```json
{
  "observability": {
    "logging": {
      "configured": true,
      "structured": true
    },
    "metrics": {
      "configured": true,
      "endpoint": "/metrics",
      "golden_signals": {
        "latency": true,
        "traffic": true,
        "errors": true,
        "saturation": true
      }
    },
    "tracing": {
      "configured": true
    },
    "dashboard": {
      "exists": true,
      "url": "https://grafana.example.com/d/abc123"
    },
    "alerts": {
      "configured": true,
      "count": 5
    },
    "summary": {
      "has_logging": true,
      "has_metrics": true,
      "has_tracing": true,
      "has_dashboard": true,
      "has_alerts": true,
      "golden_signals_complete": true
    }
  }
}
```

**Key policy paths:**
- `.observability.metrics.golden_signals.<signal>` — Signal monitored
- `.observability.dashboard.exists` — Dashboard configured
- `.observability.alerts.configured` — Alerting enabled
- `.observability.summary.golden_signals_complete` — All 4 signals

---

## Category: `.oncall`

On-call, incident management, runbooks. **Normalized across PagerDuty, OpsGenie, etc.**

```json
{
  "oncall": {
    "source": {
      "tool": "pagerduty",
      "integration": "api"
    },
    "service": {
      "id": "PXXXXXX",
      "name": "Payment API"
    },
    "schedule": {
      "exists": true,
      "participants": 4,
      "rotation": "weekly"
    },
    "escalation": {
      "exists": true,
      "levels": 3
    },
    "runbook": {
      "exists": true,
      "path": "docs/runbook.md",
      "url": "https://wiki.example.com/payment-api/runbook"
    },
    "sla": {
      "defined": true,
      "response_minutes": 15,
      "uptime_percentage": 99.9
    },
    "summary": {
      "has_oncall": true,
      "has_escalation": true,
      "has_runbook": true,
      "has_sla": true,
      "min_participants": 4
    }
  }
}
```

**Key policy paths:**
- `.oncall` — On-call configured (use `assert_exists(".oncall")`)
- `.oncall.schedule.participants` — Rotation size
- `.oncall.runbook.exists` — Runbook present
- `.oncall.sla.defined` — SLA documented

---

## Category: `.compliance`

Compliance and regulatory data.

```json
{
  "compliance": {
    "regimes": ["soc2", "pci-dss"],
    "data_classification": {
      "level": "confidential",
      "contains_pii": true,
      "contains_pci": true
    },
    "controls": {
      "access_reviews": true,
      "audit_logging": true,
      "encryption_at_rest": true,
      "encryption_in_transit": true
    }
  }
}
```

**Key policy paths:**
- `.compliance.regimes` — Applicable regimes
- `.compliance.data_classification.contains_pii` — PII flag
- `.compliance.controls.<control>` — Control status

---

## Category: `.api`

API specifications.

```json
{
  "api": {
    "spec_exists": true,
    "specs": [
      {
        "type": "openapi",
        "path": "api/openapi.yaml",
        "valid": true,
        "version": "3.0.3"
      }
    ],
    "endpoints_documented": true,
    "all_secured": true
  }
}
```

**Key policy paths:**
- `.api.spec_exists` — API spec present
- `.api.specs[].valid` — Spec is valid
- `.api.all_secured` — All endpoints have auth

---

## Naming Conventions

### Boolean Fields
- **Existence:** `exists`, `configured`, `enabled`
- **Presence aggregates:** `has_<thing>` (e.g., `has_critical`, `has_runbook`)
- **State:** `is_<state>` (e.g., `is_latest`, `is_pinned`)
- **All-aggregates:** `all_<condition>` (e.g., `all_valid`, `all_passing`)
- **Clean state:** `clean` (no issues found)

### Numeric Fields
- Include units: `duration_seconds`, `latency_ms`
- Use `_count` for quantities: `error_count`, `file_count`
- Use `_percentage` for percentages: `coverage_percentage`

### Arrays
- Plural names: `files`, `findings`, `issues`, `containers`
- Each item has identifying context: `path`, `name`, `id`

### Source Metadata
- `source.tool` — Tool name (e.g., "snyk", "trivy")
- `source.version` — Tool version
- `source.integration` — How collected: `ci`, `github_app`, `code`, `api`
- `source.collected_at` — Timestamp (ISO 8601)

### Errors
- `valid: boolean` — Parse/validation success
- `error: string` — Error message (only when `valid: false`)
- `errors: array` — Multiple errors

### Summary Objects
- Use `.summary` for aggregated/derived booleans that simplify policies
- Example: `.k8s.summary.all_have_resources` instead of iterating all containers

---

## Writing Tool-Agnostic Policies

**Good:** Check normalized fields

```python
with Check("sca-no-critical", "No critical SCA vulnerabilities") as c:
    c.assert_exists(".sca", "SCA scanner must be configured")
    c.assert_equals(c.get_value(".sca.vulnerabilities.critical"), 0,
        "Critical vulnerabilities found")
```

**Bad:** Check specific tool

```python
# Don't do this unless compliance requires a specific tool
with Check("must-use-snyk") as c:
    c.assert_equals(c.get_value(".sca.source.tool"), "snyk")
```

**When to check specific tools:** Only when compliance/policy explicitly mandates a particular scanner (e.g., "must use Snyk Enterprise for SCA").

---

## Extending the Schema

When adding new data:

1. **Does it fit an existing category?** — Don't create new top-level keys unnecessarily
2. **Is it tool-specific or capability-specific?** — Name for the capability, not the tool
3. **Can multiple tools provide this data?** — Design for normalization
4. **Include source metadata** — So policies CAN check tools if needed
5. **Add summary fields** — Make common policy checks easy
6. **Document the contract** — Update this file and collector/policy READMEs
