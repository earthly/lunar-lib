# Component JSON Conventions

This document defines the design principles and conventions for the Component JSON—the central data contract between collectors and policies.

**See also:** [structure.md](structure.md) for the standard structure of each category (`.repo`, `.sca`, `.k8s`, etc.).

## Design Principles

1. **Categories describe WHAT, not HOW** — Top-level keys represent the type of information, not the tool that collected it
2. **Tool-agnostic normalization** — Different tools producing the same type of data should populate the same paths
3. **One policy, many tools** — A policy checking "no critical SCA vulnerabilities" should work whether data came from Snyk, Semgrep, Dependabot, or any other tool
4. **Source metadata is secondary** — Tool name, version, and integration method are captured but don't dictate structure
5. **Flexible integration methods** — Same structure whether collected from CI hooks, GitHub Apps, code analysis, or external APIs
6. **Language-specific data is a valid exception** — When data and policies are inherently tied to a specific programming language's ecosystem, preserving native terminology (via `.lang.<language>`) is often clearer than forced normalization

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

## Presence Detection: Object Existence vs Explicit Booleans

There are two patterns for detecting whether something happened or exists:

### Pattern 1: Object Presence = The Signal

When a collector **only runs under certain conditions** (CI hook, cron, etc.), the **presence of the object itself** signals that the thing happened:

```json
// SCA scanner ran — .sca object exists with data:
{
  "sca": {
    "source": { "tool": "snyk" },
    "vulnerabilities": { "critical": 0, "high": 1 }
  }
}

// SCA scanner didn't run — .sca object is missing entirely
// (no .sca key in the component JSON)
```

**Policy pattern:** Use `assert_exists(...)`:
```python
c.assert_exists(".sca", "SCA scanner must be configured to run")
```

**For "ran but nothing to report" cases**, write an empty object or minimal structure:
```bash
# Minimal: empty object is valid — presence alone signals the tool ran
lunar collect -j ".sca" '{}'

# Better: include source metadata for traceability
lunar collect -j ".sca" '{"source": {"tool": "snyk"}}'
```

This is the idiomatic way to record that a tool executed without needing a boolean field.

### Pattern 2: Explicit Booleans

When a collector **always runs** (e.g., code collector that checks file existence), use explicit `true`/`false` values:

```json
{
  "repo": {
    "readme": {
      "exists": true,    // Collector always writes true OR false
      "path": "README.md"
    }
  }
}

// When file is missing:
{
  "repo": {
    "readme": {
      "exists": false    // Explicitly false, not missing
    }
  }
}
```

**Policy pattern:** Use `assert_true(get_value(...))`:
```python
c.assert_true(c.get_value(".repo.readme.exists"), "README.md not found")
```

### Anti-Pattern: Boolean Fields Without a Failure Writer

**Avoid** using boolean fields like `.sca.ran` when the collector cannot write `false` for the failure case:

```json
// BAD: .sca.ran is always true when present, never false
{
  "sca": {
    "ran": true,  // ❌ Misleading — this field can only ever be true
    "vulnerabilities": { ... }
  }
}
```

**Why it's problematic:**
- If the SCA scanner doesn't run, there's no collector to write `"ran": false`
- The field only ever contains `true`, making it redundant
- Policy authors might incorrectly use `assert_true(get_value(".sca.ran"))`, which fails with "no data" instead of a meaningful message

**Correct approach:** Let the object's presence be the signal:

```json
// GOOD: Object exists = scanner ran
{
  "sca": {
    "source": { "tool": "snyk" },
    "vulnerabilities": { ... }
  }
}
```

**When IS a boolean appropriate?** When the same collector can write both `true` and `false`:

```json
// GOOD: Code collector always runs and checks file existence
{
  "repo": {
    "readme": {
      "exists": true   // Same collector writes false when file missing
    }
  }
}
```

### Summary Table

| Scenario | Collector Behavior | Policy Assertion |
|----------|-------------------|------------------|
| Conditional execution (CI hook, scanner) | Object exists when ran, missing when didn't | `assert_exists(".sca")` |
| Always-checked property | Writes explicit `true` or `false` | `assert_true(get_value(".repo.readme.exists"))` |

### Optional Fields in Nested Data

For optional fields **within** already-collected data (like optional K8s manifest fields), use `get_value_or_default()`:

```python
# K8s namespace is optional, defaults to "default"
ns = desc.get_value_or_default(".contents.metadata.namespace", "default")
```

---

## PR-Specific Data

Some data only applies in PR context (scanners that only run on PRs, PR metadata, etc.). This is handled as a first-class concern.

### The `.pr` Sub-Key Pattern

Within any category, use a `.pr` sub-key for PR-specific data:

```json
{
  "sca": {
    "source": { "tool": "snyk" },
    "vulnerabilities": { "critical": 0, "high": 1 },
    "pr": {
      "new_vulnerabilities": { "critical": 0, "high": 0 },
      "fixed_vulnerabilities": { "high": 1 }
    }
  }
}
```

**Note:** The `.sca` object's presence signals the scanner ran (see [Presence Detection](#presence-detection-object-existence-vs-explicit-booleans)).

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

## Language-Specific Data

When data is fundamentally tied to a particular programming language's ecosystem, conventions, or tooling—and when policies are only meaningful for that language—it may be better to preserve language-native terminology rather than forcing artificial normalization.

### When to Use Language-Specific Paths

**Use `.lang.<language>` when:**
1. **Data semantics are language-specific** — Go modules vs npm packages vs Cargo crates have different meanings
2. **Policies only apply to that language** — No benefit to forcing a generic structure
3. **Normalization would lose meaning** — "workspace" means different things in different ecosystems
4. **Tools and concepts don't translate** — Rust's borrow checker findings, Go's race detector results, Java's annotation processing

**Prefer normalization when:**
1. **Cross-language policies exist** — "All services must have dependency lockfiles"
2. **Concepts translate cleanly** — Test coverage percentages, vulnerability counts, dependency totals
3. **Dashboards compare languages** — "Go services vs Java services coverage"

### The `.lang.<language>` Pattern

For language-specific data, use `.lang.<language_name>`:

**Java example:**

```json
{
  "lang": {
    "java": {
      "version": "17",
      "build_system": "maven",
      "group_id": "com.acme",
      "artifact_id": "payment-api",
      "packaging": "jar",
      "spotbugs": {
        "high": 0,
        "medium": 2,
        "low": 8
      },
      "checkstyle": {
        "violations": 15
      },
      "pmd": {
        "violations": 3
      }
    }
  }
}
```

### Build System Variations

Within a language, different build systems (e.g., Maven vs Gradle, npm vs yarn vs pnpm) may warrant their own structure. The recommendation:

- **Use `build_systems` as an array** — Projects may use multiple build tools (e.g., Gradle for builds + Maven for publishing)
- **Store full dependency arrays** — Enable language-specific version policies for example replace directive tracking in go
- **Use `.native.<build_system>` for build-system specifics** — When raw config details are needed

```json
{
  "lang": {
    "java": {
      "version": "17",
      "build_systems": ["gradle", "maven"],
      "dependencies": {
        "direct": [
          {"path": "com.google.guava:guava", "version": "31.0.1"}
        ],
        "transitive": [
          {"path": "org.checkerframework:checker-qual", "version": "3.12.0"}
        ]
      },
      "native": {
        "gradle": {
          "version": "8.5",
          "kotlin_dsl": true,
          "plugins": ["java", "org.springframework.boot", "com.github.spotbugs"],
          "subprojects": ["api", "client", "common"],
          "build_cache_enabled": true
        },
        "maven": {
          "version": "3.9.6",
          "plugins": ["maven-publish", "maven-gpg-plugin"],
          "profiles": ["release", "ci"]
        }
      }
    }
  }
}
```

### Relationship to Normalized Categories

The `.lang` category complements, not replaces, normalized categories:

| Data Type | Normalized Path | Language-Specific Path |
|-----------|-----------------|------------------------|
| Dependency vulnerabilities | `.sca.vulnerabilities` | — (always normalize) |
| Test coverage percentage | `.testing.coverage.percentage` | — (always normalize) |
| Linter findings | `.sast.findings` (if security-focused) | `.lang.go.golangci_lint` (if language-specific) |
| Build tool config | — | `.lang.java.native.maven` |
| Language-specific safety | — | `.lang.rust.unsafe_blocks` |

**Rule of thumb:** If a policy could reasonably apply across multiple languages, normalize the data. If the policy only makes sense for one language, use `.lang.<language>`.

### `.lang.<language>.dependencies` vs `.sbom`

Both capture dependency information, but serve different purposes:

| Use Case | Best Source | Why |
|----------|-------------|-----|
| **Dependency version policies** | `.lang.<lang>.dependencies` | Supports language-native version semantics |
| **License compliance** | `.sbom` | SPDX license identifiers, cross-language |
| **Vulnerability scanning** | `.sca` / `.sbom` | CVE correlation via CPE/PURL |
| **"No GPL dependencies"** | `.sbom` | License data, cross-language |

**Why keep both?**

1. **Language-native data in `.lang.<lang>.dependencies`:**
   - Replace directives (Go `replace`, npm `overrides`) — often missed by SBOMs
   - Direct vs transitive distinction with language semantics
   - Exact toolchain resolution (what the build actually uses)
   - No SBOM tooling required
   - Enables version policies with language-aware comparison

2. **Standardized data in `.sbom`:**
   - License information (SPDX identifiers)
   - Cross-language policies (single policy for Go, Java, Node)
   - Vulnerability correlation via PURL
   - Compliance requirements (many frameworks mandate SBOM)

**Version comparison note:** Version strings remain language-native in both sources (`v1.2.3` for Go, `1.2.3-SNAPSHOT` for Maven). Policies checking minimum versions should normalize versions for comparison, handling prefixes (`v`), suffixes (`-SNAPSHOT`, `+incompatible`), and special formats (Go pseudo-versions, calendar versioning).

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
6. **Document the contract** — Update the structure docs and collector/policy READMEs
