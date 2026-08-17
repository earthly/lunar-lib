# Dependency Guardrails

Policies for validating project dependencies.

## Overview

This policy plugin validates that project dependencies meet organizational requirements — both which versions are used and where they are resolved from. It's useful for enforcing security patches, mandating upgrades for dependencies with known vulnerabilities, and requiring that packages come from an approved registry rather than a public index. Version policies read the standardized `.lang.{language}.dependencies` paths, and registry policies read `.dependencies.registries`.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `min-versions` | Ensures dependencies meet minimum safe versions | One or more dependencies are below the required minimum version |
| `approved-registries` | Restricts dependency resolution to approved registries | A registry outside the allowlist is configured, or the project silently resolves from a public index |
| `no-public-registries` | Requires that no dependency resolves from a public index | A well-known public registry (npmjs, PyPI, Maven Central, RubyGems, NuGet) is in use |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.{language}.dependencies.direct` | array | Language-specific collectors (e.g., [`golang`](https://github.com/earthly/lunar-lib/tree/main/collectors/golang)) |
| `.lang.{language}.dependencies.direct[].path` | string | Dependency identifier |
| `.lang.{language}.dependencies.direct[].version` | string | Version string |
| `.lang.{language}.dependencies.indirect` | array | Language-specific collectors (when `include_indirect` is enabled) |
| `.dependencies.registries[]` | array | [`package-registries`](https://github.com/earthly/lunar-lib/tree/main/collectors/package-registries) collector |
| `.dependencies.registries[].host` | string | Registry hostname matched against the allowlist |
| `.dependencies.registries[].ecosystem` | string | Ecosystem the registry serves |
| `.dependencies.registries[].is_public` | boolean | Whether the host is a well-known public index |

**Note:** Ensure the corresponding collector is configured before enabling a policy — the language
collector for `min-versions`, and the `package-registries` collector for the registry policies. The
registry policies skip components with no `.dependencies` data, so a repository with no package
manager is not penalized.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dependencies@v1.0.0
    include: [min-versions]
    on: ["lang:go"]  # Or use appropriate tags
    enforcement: block-pr
    with:
      language: "go"
      min_versions: '{"github.com/example/lib": "1.2.0", "golang.org/x/crypto": "0.17.0"}'
      # include_indirect: "true"  # Optional: also check transitive dependencies
```

The registry policies take a separate allowlist, so they are usually imported as their own entry:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dependencies@v1.0.0
    name: registry-provenance
    include: [approved-registries]
    on: ["domain:your-domain"]
    enforcement: block-pr
    with:
      allowed_registries: "dl.cloudsmith.io"
```

Requires the [`package-registries`](https://github.com/earthly/lunar-lib/tree/main/collectors/package-registries)
collector. `approved-registries` errors if `allowed_registries` is empty — an allowlist with no
entries would fail every component. Use `no-public-registries` instead when you want the zero-config
form.

## Examples

### Passing Example

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

### Failing Example

```json
{
  "lang": {
    "go": {
      "dependencies": {
        "direct": [
          {"path": "github.com/example/lib", "version": "v1.1.0"}
        ]
      }
    }
  }
}
```

**Failure message:** `"'github.com/example/lib' version v1.1.0 is below minimum safe version 1.2.0"`

### Registry Provenance — Passing Example

With `allowed_registries: "dl.cloudsmith.io"`:

```json
{
  "dependencies": {
    "registries": [
      {
        "ecosystem": "npm",
        "host": "dl.cloudsmith.io",
        "path": ".npmrc",
        "is_default": false,
        "is_public": false
      }
    ]
  }
}
```

### Registry Provenance — Failing Example

A project with a `package.json` but no `.npmrc`, so npm resolves from the public registry:

```json
{
  "dependencies": {
    "registries": [
      {
        "ecosystem": "npm",
        "host": "registry.npmjs.org",
        "path": "package.json",
        "is_default": true,
        "is_public": true
      }
    ]
  }
}
```

**Failure message:** `"npm resolves from 'registry.npmjs.org' (ecosystem default, no registry configured in package.json) which is not in allowed registries: dl.cloudsmith.io"`

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

### Registry Provenance

Point the package manager at the approved registry. The fix is a committed config file, so the
guardrail cannot be satisfied by removing configuration — a project with no registry config is
reported as resolving from its ecosystem's public default.

```bash
# npm — writes registry= to .npmrc
npm config set registry https://dl.cloudsmith.io/basic/acme/npm/ --location project

# pip — .pip/pip.conf or pip.conf at the repo root
printf '[global]\nindex-url = https://dl.cloudsmith.io/basic/acme/python/simple/\n' > pip.conf

# Maven — add a <mirror> to settings.xml, or a <repository> to pom.xml
# Gradle — replace mavenCentral() with maven { url "https://dl.cloudsmith.io/..." }
# RubyGems — source "https://dl.cloudsmith.io/basic/acme/gems/" in the Gemfile
# NuGet — nuget.config <packageSources>, with <clear/> before <add ... />
```

For NuGet and pip, remember to remove or override the public source as well — adding an internal
source alongside `nuget.org` or leaving an `--extra-index-url` still allows public resolution.

### Version Format Issues

If you see "Cannot parse version" errors, ensure versions follow semver format:

- **Supported:** `1.2.3`, `v1.2.3`, `1.0.0-alpha`, `1.0.0-beta.1`
- **Go pseudo-versions:** `v0.0.0-20240101-abcdef` (parsed as prerelease)
- **Not supported:** Date-based (`2024.01.15`), CalVer (`2024.1`), or non-numeric (`latest`)
