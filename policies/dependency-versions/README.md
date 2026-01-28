# `dependency-versions` Policy

Checks that dependencies meet minimum safe version requirements.

## Overview

This policy validates that project dependencies are at or above specified minimum versions. It's useful for enforcing security patches, ensuring compatibility with internal libraries, or mandating upgrades for dependencies with known vulnerabilities. The policy works across multiple languages by reading from the standardized `.lang.{language}.dependencies.direct` path.

## Policies

This plugin provides the following policies:

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `dependency-versions` | Ensures dependencies meet minimum safe versions | One or more dependencies are below the required minimum version |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.{language}.dependencies.direct` | array | Language-specific collectors (e.g., `golang`) |
| `.lang.{language}.dependencies.direct[].path` | string | Dependency identifier |
| `.lang.{language}.dependencies.direct[].version` | string | Version string |

**Note:** Ensure the corresponding language collector is configured before enabling this policy.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `language` | **Yes** | `""` | Programming language to check (e.g., `"go"`, `"java"`, `"python"`, `"nodejs"`) |
| `min_versions` | No | `"{}"` | JSON object mapping dependency paths to minimum safe versions |

**Note:** The `language` input is required. The policy will error if not specified.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dependency-versions@v1.0.0
    on: ["lang:go"]  # Or use appropriate tags
    enforcement: block-pr
    with:
      language: "go"
      min_versions: '{"github.com/example/lib": "1.2.0", "golang.org/x/crypto": "0.17.0"}'
```

## Examples

### Passing Example

Component has dependencies at or above minimum versions:

```json
{
  "lang": {
    "go": {
      "dependencies": {
        "direct": [
          {"path": "github.com/example/lib", "version": "v1.3.0"},
          {"path": "golang.org/x/crypto", "version": "v0.18.0"}
        ]
      }
    }
  }
}
```

With configuration:
```yaml
with:
  language: "go"
  min_versions: '{"github.com/example/lib": "1.2.0", "golang.org/x/crypto": "0.17.0"}'
```

Result: **PASS** (both dependencies meet or exceed minimum versions)

### Failing Example

Component has a dependency below minimum version:

```json
{
  "lang": {
    "go": {
      "dependencies": {
        "direct": [
          {"path": "github.com/example/lib", "version": "v1.1.0"},
          {"path": "golang.org/x/crypto", "version": "v0.18.0"}
        ]
      }
    }
  }
}
```

**Failure message:** `"'github.com/example/lib' version v1.1.0 is below minimum safe version 1.2.0"`

### No Requirements Configured

When `min_versions` is empty (`"{}"`), the policy passes with no assertions:

```yaml
with:
  language: "go"
  min_versions: "{}"
```

Result: **PASS** (no minimum version requirements configured)

## Related Collectors

This policy works with any collector that populates `.lang.{language}.dependencies.direct`:

- [`golang`](https://github.com/earthly/lunar-lib/tree/main/collectors/golang) — Collects Go module dependencies

## Remediation

When this policy fails, update the affected dependency to meet the minimum version:

### Go

```bash
go get github.com/example/lib@v1.2.0
go mod tidy
```

### Node.js

```bash
npm install example-lib@1.2.0
```

### Python

```bash
pip install "example-lib>=1.2.0"
# Update requirements.txt or pyproject.toml accordingly
```

### Java (Maven)

Update `pom.xml`:
```xml
<dependency>
  <groupId>com.example</groupId>
  <artifactId>lib</artifactId>
  <version>1.2.0</version>
</dependency>
```

## Version Parsing

This policy uses [semver](https://python-semver.readthedocs.io/) for version comparison. It handles:

- Standard semver versions: `1.2.3`
- Versions with `v` prefix: `v1.2.3` (prefix is stripped before comparison)

**Limitations:**
- Non-semver versions (e.g., Go pseudo-versions like `v0.0.0-20240101120000-abcdef123456`) will cause the check to fail with a parse error
- Calendar versioning or other non-semver schemes are not supported
