# `dependencies` Policies

Policies for validating project dependencies.

## Overview

This policy plugin validates that project dependencies meet organizational requirements. It's useful for enforcing security patches, ensuring compatibility with internal libraries, or mandating upgrades for dependencies with known vulnerabilities. The policies work across multiple languages by reading from the standardized `.lang.{language}.dependencies` paths.

## Policies

This plugin provides the following policies:

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `min-versions` | Ensures dependencies meet minimum safe versions | One or more dependencies are below the required minimum version |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.{language}.dependencies.direct` | array | Language-specific collectors (e.g., `golang`) |
| `.lang.{language}.dependencies.direct[].path` | string | Dependency identifier |
| `.lang.{language}.dependencies.direct[].version` | string | Version string |
| `.lang.{language}.dependencies.indirect` | array | Language-specific collectors (when `include_indirect` is enabled) |

**Note:** Ensure the corresponding language collector is configured before enabling this policy.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `language` | **Yes** | `""` | Programming language to check (e.g., `"go"`, `"java"`, `"python"`, `"nodejs"`) |
| `min_versions` | No | `"{}"` | JSON object mapping dependency paths to minimum safe versions |
| `include_indirect` | No | `"false"` | Whether to also check indirect (transitive) dependencies |

**Note:** The `language` input is required. The policy will error if not specified. Versions must follow [semver](https://semver.org/) format (e.g., `1.2.3`). Date-based versioning (e.g., `2024.01.15`) and CalVer schemes are not supported.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dependencies@v1.0.0
    on: ["lang:go"]  # Or use appropriate tags
    enforcement: block-pr
    with:
      language: "go"
      min_versions: '{"github.com/example/lib": "1.2.0", "golang.org/x/crypto": "0.17.0"}'
      # include_indirect: "true"  # Optional: also check transitive dependencies
```

## Examples

### Passing Example

```json
{"lang": {"go": {"dependencies": {"direct": [{"path": "github.com/example/lib", "version": "v1.3.0"}]}}}}
```

### Failing Example

```json
{"lang": {"go": {"dependencies": {"direct": [{"path": "github.com/example/lib", "version": "v1.0.0"}]}}}}
```

## Related Collectors

This policy works with any collector that populates `.lang.{language}.dependencies.direct`:

- [`golang`](https://github.com/earthly/lunar-lib/tree/main/collectors/golang) — Collects Go module dependencies

## Remediation

When this policy fails, update the affected dependency to meet the minimum version:

```bash
# Go
go get github.com/example/lib@v1.2.0 && go mod tidy

# Node.js
npm install example-lib@1.2.0

# Python
pip install "example-lib>=1.2.0"
```

### Version Format Issues

If you see "Cannot parse version" errors, ensure versions follow semver format:

- **Supported:** `1.2.3`, `v1.2.3`, `1.0.0-alpha`, `1.0.0-beta.1`
- **Go pseudo-versions:** `v0.0.0-20240101-abcdef` (parsed as prerelease)
- **Not supported:** Date-based (`2024.01.15`), CalVer (`2024.1`), or non-numeric (`latest`)
