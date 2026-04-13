# Ruby Project Guardrails

Enforces Ruby project structure, dependency management, and security standards.

## Overview

This policy enforces Ruby-specific engineering standards including Gemfile presence, lockfile management for reproducible builds, Ruby version pinning, and vulnerability-free dependencies via bundler-audit. It applies to any component with Ruby project indicators and skips gracefully when no Ruby project is detected.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `gemfile-exists` | Ensures a Gemfile is present for dependency management |
| `lockfile-exists` | Ensures Gemfile.lock exists for reproducible dependency resolution |
| `ruby-version-set` | Ensures Ruby version is pinned via .ruby-version or Gemfile ruby directive |
| `bundler-audit-clean` | Ensures no known vulnerabilities in gem dependencies (skips if no audit data) |
| `min-ruby-version` | Ensures project Ruby version meets the configured minimum |
| `min-ruby-version-cicd` | Ensures Ruby version used in CI/CD meets the configured minimum |
| `min-bundler-version-cicd` | Ensures Bundler version used in CI/CD meets the configured minimum |
| `min-rake-version-cicd` | Ensures Rake version used in CI/CD meets the configured minimum |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.ruby` | object | `ruby` collector |
| `.lang.ruby.gemfile_exists` | boolean | `ruby` collector (project) |
| `.lang.ruby.gemfile_lock_exists` | boolean | `ruby` collector (project) |
| `.lang.ruby.ruby_version_file_exists` | boolean | `ruby` collector (project) |
| `.lang.ruby.version` | string | `ruby` collector (project) |
| `.lang.ruby.bundler_audit.vulnerabilities` | array | `ruby` collector (bundler-audit or bundler-audit-cicd) |
| `.lang.ruby.cicd.cmds` | array | `ruby` collector (cicd) |
| `.lang.ruby.bundler.cicd.cmds` | array | `ruby` collector (bundler-cicd) |
| `.lang.ruby.rake.cicd.cmds` | array | `ruby` collector (rake-cicd) |

**Note:** Ensure the `ruby` collector is configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/ruby@main
    on: ["domain:your-domain"]
    enforcement: report-pr
    # include: [gemfile-exists, lockfile-exists]  # Only run specific checks
    # with:
    #   max_audit_vulnerabilities: "0"
    #   min_ruby_version: "3.0"
    #   min_ruby_version_cicd: "3.0"
    #   min_bundler_version_cicd: "2.4"
    #   min_rake_version_cicd: "13.0"
```

## Examples

### Passing Example

A well-configured Ruby project with all standards met:

```json
{
  "lang": {
    "ruby": {
      "version": "3.2.2",
      "gemfile_exists": true,
      "gemfile_lock_exists": true,
      "ruby_version_file_exists": true,
      "bundler_audit": {
        "vulnerabilities": [],
        "source": { "tool": "bundler-audit", "integration": "ci" }
      }
    }
  }
}
```

### Failing Example

A Ruby project missing a lockfile and with a known vulnerability:

```json
{
  "lang": {
    "ruby": {
      "version": "3.1.0",
      "gemfile_exists": true,
      "gemfile_lock_exists": false,
      "ruby_version_file_exists": false,
      "bundler_audit": {
        "vulnerabilities": [
          {
            "gem": "actionpack",
            "version": "7.0.4",
            "advisory": "CVE-2023-22795",
            "title": "ReDoS vulnerability",
            "criticality": "High"
          }
        ]
      }
    }
  }
}
```

**Failure messages:**
- `lockfile-exists`: `"Gemfile.lock not found. Run 'bundle install' and commit the lockfile for reproducible builds."`
- `ruby-version-set`: `"Ruby version not specified. Create a .ruby-version file or add a ruby directive to your Gemfile."`
- `bundler-audit-clean`: `"bundler-audit found 1 known vulnerability. Run 'bundle audit' for details and update affected gems."`

## Remediation

When this policy fails, you can resolve it by:

1. **gemfile-exists** — Initialize a Gemfile with `bundle init` or create one manually
2. **lockfile-exists** — Run `bundle install` to generate Gemfile.lock and commit it
3. **ruby-version-set** — Create a `.ruby-version` file (e.g., `echo "3.2.2" > .ruby-version`) or add `ruby "3.2.2"` to your Gemfile
4. **bundler-audit-clean** — Run `bundle audit` to see vulnerabilities, then `bundle update <gem>` to update affected gems
5. **min-ruby-version** — Update the Ruby version in `.ruby-version` or your Gemfile `ruby` directive to meet the minimum
6. **min-ruby-version-cicd** — Update the Ruby installation in your CI environment to the required minimum version
7. **min-bundler-version-cicd** — Run `gem install bundler` in CI to update to a supported Bundler version
8. **min-rake-version-cicd** — Update the `rake` gem in your Gemfile to meet the minimum version
