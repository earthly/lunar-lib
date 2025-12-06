# Component JSON Conventions

This document defines the standard structure and naming conventions for the Component JSON—the central data contract between collectors and policies.

## Design Principles

1. **Categories describe WHAT, not HOW** — Top-level keys represent the type of information, not the tool that collected it
2. **Tool-agnostic normalization** — Different tools producing the same type of data should populate the same paths
3. **One policy, many tools** — A policy checking "no critical SCA vulnerabilities" should work whether data came from Snyk, Semgrep, Dependabot, or any other tool
4. **Source metadata is secondary** — Tool name, version, and integration method are captured but don't dictate structure
5. **Flexible integration methods** — Same structure whether collected from CI hooks, GitHub Apps, code analysis, or external APIs

## Integration Methods

Data can be collected through various integration points. The structure should be the same regardless of method:

| Method | Description | Example |
|--------|-------------|---------|
| `ci` | Collected during CI pipeline execution | Running `snyk test` in CI |
| `github_app` | From GitHub App status checks | Snyk GitHub App posting results |
| `code` | Analyzed from files in repository | Parsing Dockerfiles |
| `api` | Queried from external API (cron) | Calling PagerDuty API |

---

## Source Metadata Pattern

When capturing which tool provided data, use a consistent `_source` suffix:

```json
{
  "category": {
    "field": "normalized_value",
    "field_source": {
      "tool": "snyk",
      "version": "1.1200.0",
      "integration": "github_app",
      "collected_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

Or for an entire category:

```json
{
  "category": {
    "source": {
      "tool": "trivy",
      "version": "0.48.0", 
      "integration": "ci"
    },
    "findings": { /* normalized data */ }
  }
}
```

This allows policies to:
- Check normalized data without caring about the tool
- Optionally verify a specific tool was used (if required by compliance)

---

## Presence Detection Naming

Different naming conventions signal different assertion patterns to policy authors.

### `exists` — Collector writes both `true` and `false`

Use `exists` when the collector **always runs** and explicitly records presence or absence:

```json
{
  "repo": {
    "readme": {
      "exists": true,    // Collector writes true
      "path": "README.md"
    }
  }
}

// Or when file is missing:
{
  "repo": {
    "readme": {
      "exists": false    // Collector explicitly writes false
    }
  }
}
```

**Policy pattern:** Use `assert_true(get_value(...))`:
```python
c.assert_true(c.get_value(".repo.readme.exists"), "README.md not found")
```

### `ran` — Collector only writes on execution

Use `ran` when data is only present if something executed (CI step, scanner, etc.):

```json
// When scanner ran:
{
  "sca": {
    "ran": true,
    "vulnerabilities": { ... }
  }
}

// When scanner didn't run: the entire .sca object may be missing
```

**Policy pattern:** Use `assert_exists(...)`:
```python
c.assert_exists(".sca.ran", "SCA scanner must be configured to run")
```

### `configured` — External integration status

Use `configured` for external system integrations where absence means not set up:

```json
{
  "oncall": {
    "configured": true,  // Only present if PagerDuty/etc is set up
    "service": { ... }
  }
}
```

**Policy pattern:** Use `assert_exists(...)`:
```python
c.assert_exists(".oncall.configured", "On-call must be configured")
```

### Summary Table

| Field Name | Collector Behavior | Policy Assertion |
|------------|-------------------|------------------|
| `exists` | Always writes `true` or `false` | `assert_true(get_value(...))` |
| `ran` | Only writes when executed | `assert_exists(...)` |
| `configured` | Only writes when set up | `assert_exists(...)` |
| `found` | Only writes when detected | `assert_exists(...)` |

---

## PR-Specific Data

Some data only applies in PR context (scanners that only run on PRs, PR metadata, etc.). This is handled as a first-class concern.

### The `.pr` Sub-Key Pattern

Within any category, use a `.pr` sub-key for PR-specific data:

```json
{
  "sca": {
    "ran": true,
    "vulnerabilities": { "critical": 0, "high": 1 },
    "pr": {
      "scan_ran": true,
      "new_vulnerabilities": { "critical": 0, "high": 0 },
      "fixed_vulnerabilities": { "high": 1 }
    }
  }
}
```

### The `.vcs.pr` Object

PR metadata lives in `.vcs.pr`:

```json
{
  "vcs": {
    "provider": "github",
    "pr": {
      "number": 123,
      "title": "[ABC-456] Add payment validation",
      "description": "This PR adds validation for...",
      "author": "jdoe",
      "labels": ["enhancement", "payments"],
      "reviewers": ["alice", "bob"],
      "approved": true,
      "ticket": {
        "id": "ABC-456",
        "source": "jira"
      },
      "commits": 3,
      "files_changed": 12
    }
  }
}
```

### Checking PR Context in Policies

Policies can check if they're in a PR context:

```python
# Data that only exists in PR context
if c.exists(".vcs.pr"):
    # PR-specific assertions
    c.assert_exists(".vcs.pr.ticket.id", "PR must reference a ticket")
    
# Data that might have PR-specific details
if c.exists(".sca.pr.new_vulnerabilities"):
    c.assert_equals(c.get_value(".sca.pr.new_vulnerabilities.critical"), 0,
        "PR introduces critical vulnerabilities")
```

### Environment Variable

Collectors can check `LUNAR_COMPONENT_PR` to know if they're in PR context:

```bash
if [ -n "$LUNAR_COMPONENT_PR" ]; then
  # Collect PR-specific data
  lunar collect -j ".vcs.pr.number" "$LUNAR_COMPONENT_PR"
fi
```

---

## Raw/Native Data

While normalization is ideal, sometimes it's impractical or lossy. Use the `.native` sub-key for tool-specific or format-specific raw data.

### When to Use `.native`

1. **Normalization is too complex** — Full SBOM data, Terraform HCL
2. **Multiple formats exist** — SPDX vs CycloneDX SBOMs
3. **Raw data is valuable** — Policies may need tool-specific fields
4. **Incremental adoption** — Collect raw now, normalize later

### The `.native` Pattern

Place normalized data at the category level, raw data under `.native.<format>` or `.native.<tool>`:

```json
{
  "sbom": {
    "generated": true,
    "source": {
      "tool": "syft",
      "format": "spdx-json"
    },
    "summary": {
      "packages": 156,
      "licenses": ["MIT", "Apache-2.0", "BSD-3-Clause"]
    },
    "native": {
      "spdx": {
        "spdxVersion": "SPDX-2.3",
        "documentNamespace": "https://...",
        "packages": [ /* full SPDX package array */ ]
      }
    }
  }
}
```

### Multiple Tools/Formats Example

When multiple tools contribute to the same category:

```json
{
  "sbom": {
    "generated": true,
    "summary": {
      "packages": 156
    },
    "native": {
      "spdx": { /* SPDX format from syft */ },
      "cyclonedx": { /* CycloneDX format from cdxgen */ }
    }
  }
}
```

### IaC Example (Terraform)

```json
{
  "iac": {
    "tool": "terraform",
    "analysis": {
      "internet_accessible": true,
      "has_waf": true,
      "datastores": {
        "all_deletion_protected": true
      }
    },
    "native": {
      "terraform": {
        "files": [
          {
            "path": "main.tf",
            "hcl": { /* parsed HCL as JSON */ }
          }
        ],
        "providers": ["aws", "random"],
        "modules": ["vpc", "rds"]
      }
    }
  }
}
```

### Policy Patterns for Native Data

**Prefer normalized data when available:**
```python
# Good - uses normalized field
c.assert_true(c.get_value(".iac.datastores.all_deletion_protected"),
    "All datastores must have deletion protection")
```

**Fall back to native when necessary:**
```python
# When you need tool-specific details
tf_files = c.get_node(".iac.native.terraform.files")
if tf_files.exists():
    for f in tf_files:
        # Deep inspection of Terraform HCL
        hcl = f.get_value(".hcl")
        # ... custom logic ...
```

**Handle multiple sources:**
```python
# Check SBOM from any format
sbom = c.get_node(".sbom")
if not sbom.exists():
    c.fail("SBOM not generated")
    return

# Use normalized summary
packages = c.get_value(".sbom.summary.packages")

# If you need raw data, check what's available
native = sbom.get_node(".native")
if native.exists():
    if c.exists(".sbom.native.spdx"):
        # Process SPDX format
        pass
    elif c.exists(".sbom.native.cyclonedx"):
        # Process CycloneDX format
        pass
```

### Guidelines for `.native`

1. **Always provide normalized summary** — Even with native data, extract key facts
2. **Use format/tool names as keys** — `.native.spdx`, `.native.terraform`, `.native.snyk`
3. **Document what's in native** — Collector README should explain the structure
4. **Prefer normalized in policies** — Only dive into `.native` when necessary
5. **Native can be large** — Consider what's actually useful vs. dumping everything

---

## Top-Level Categories

| Key | Description |
|-----|-------------|
| `.repo` | Repository structure, README, standard files |
| `.ownership` | Code ownership, maintainers, team info |
| `.catalog` | Service catalog entries (Backstage, etc.) |
| `.vcs` | Version control settings (branch protection, etc.) |
| `.dependencies` | Package dependencies from lock files |
| `.sbom` | Software Bill of Materials |
| `.containers` | Container images, Dockerfiles, registries |
| `.k8s` | Kubernetes manifests and configuration |
| `.iac` | Infrastructure as Code (Terraform, Pulumi, etc.) |
| `.ci` | CI/CD pipeline execution and configuration |
| `.testing` | Test execution results and code coverage |
| `.sca` | Software Composition Analysis (dependency vulnerabilities) |
| `.sast` | Static Application Security Testing |
| `.secrets` | Secret/credential scanning |
| `.container_scan` | Container image vulnerability scanning |
| `.observability` | Monitoring, logging, tracing configuration |
| `.oncall` | On-call, incident management, runbooks |
| `.compliance` | Compliance regime data |
| `.api` | API specifications and documentation |
| `.runtime` | Production/runtime data from cron collectors |

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
            "registry": "docker.io",
            "tag": "1.21-alpine",
            "is_latest": false,
            "is_pinned": true
          }
        ],
        "final_stage": {
          "base_image": "gcr.io/distroless/static:nonroot",
          "user": "nonroot",
          "runs_as_root": false,
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
    "registries_used": ["docker.io", "gcr.io"],
    "summary": {
      "uses_latest_tag": false,
      "all_non_root": true,
      "all_have_labels": true
    }
  }
}
```

**Key policy paths:**
- `.containers.definitions[].valid` — Dockerfile valid
- `.containers.definitions[].final_stage.runs_as_root` — Root user check
- `.containers.definitions[].base_images[].is_latest` — Latest tag used
- `.containers.builds[].signed` — Image signed
- `.containers.registries_used` — Registries for allowlist checking
- `.containers.summary.uses_latest_tag` — Any latest tag

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
    "ran": true,
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
      "ran": true,
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
- `.testing.ran` — Tests executed
- `.testing.results.failed` — Failure count
- `.testing.all_passing` — Clean test run
- `.testing.coverage.ran` — Coverage collected
- `.testing.coverage.percentage` — Overall coverage
- `.testing.coverage.meets_threshold` — Above minimum

---

## Category: `.sca`

Software Composition Analysis (dependency vulnerabilities). **Normalized across Snyk, Dependabot, Semgrep, Grype, etc.**

```json
{
  "sca": {
    "ran": true,
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
- `.sca.ran` — SCA scan executed
- `.sca.vulnerabilities.critical` — Critical count
- `.sca.summary.has_critical` — Any criticals
- `.sca.source.tool` — Which tool (if compliance requires specific tool)

**Note:** Policies should check `.sca.ran` and `.sca.vulnerabilities`, NOT `.sca.source.tool` (unless compliance mandates a specific scanner).

---

## Category: `.sast`

Static Application Security Testing. **Normalized across Semgrep, SonarQube, CodeQL, etc.**

```json
{
  "sast": {
    "ran": true,
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
- `.sast.ran` — SAST scan executed
- `.sast.findings.critical` — Critical findings
- `.sast.summary.has_critical` — Any criticals

---

## Category: `.secrets`

Secret/credential scanning. **Normalized across Gitleaks, TruffleHog, detect-secrets, etc.**

```json
{
  "secrets": {
    "ran": true,
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
- `.secrets.ran` — Secret scan executed
- `.secrets.findings.total` — Secrets found
- `.secrets.clean` — No secrets detected

---

## Category: `.container_scan`

Container image vulnerability scanning. **Normalized across Trivy, Grype, Clair, etc.**

```json
{
  "container_scan": {
    "ran": true,
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
- `.container_scan.ran` — Scan executed
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
    "configured": true,
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
- `.oncall.configured` — On-call set up
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
    c.assert_exists(".sca.ran", "SCA scanner must be configured")
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
