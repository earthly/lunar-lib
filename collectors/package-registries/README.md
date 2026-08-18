# Package Registries Collector

Records which package registries a repository resolves its dependencies from, across npm, pip, Maven, Gradle, RubyGems and NuGet.

## Overview

This collector reads package-manager configuration that is already committed to the repository and
normalizes the registry hosts each ecosystem resolves dependencies from. It runs as a code
collector on the Lunar runner and needs no registry credentials or API token. When an ecosystem's
manifest is present but declares no registry, the collector records that ecosystem's public
default instead of staying silent, so a repository that implicitly pulls from a public index is
still visible to guardrails.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.dependencies.source` | object | Tool metadata (`tool`, `integration`) |
| `.dependencies.ecosystems[]` | array | Package ecosystems detected in the repository |
| `.dependencies.registries[]` | array | One entry per registry declaration found |
| `.dependencies.registries[].ecosystem` | string | `npm`, `pip`, `maven`, `gradle`, `rubygems` or `nuget` |
| `.dependencies.registries[].host` | string | Registry hostname — what allowlists are matched against |
| `.dependencies.registries[].url` | string | Registry URL as declared (or the ecosystem default) |
| `.dependencies.registries[].path` | string | File the declaration was read from |
| `.dependencies.registries[].name` | string | Declaration identifier where one exists (npm scope, Maven repo id, NuGet source key) |
| `.dependencies.registries[].kind` | string | Role of the declaration: `primary`, `extra`, `mirror`, `plugin` or `publish` |
| `.dependencies.registries[].is_default` | boolean | `true` when no registry was declared and the ecosystem's public default applies |
| `.dependencies.registries[].is_public` | boolean | `true` when the host is a well-known public package index |
| `.dependencies.registries_used[]` | array | Deduplicated registry hostnames across all ecosystems |
| `.dependencies.summary.has_public` | boolean | `true` when any resolved registry is a public index |

Repositories with no package-manager configuration and no recognized manifest produce no
`.dependencies` object at all, so guardrails that read it skip cleanly.

### Implicit defaults are recorded

A repository with a `package.json` but no `.npmrc` resolves from `registry.npmjs.org`. Rather than
reporting nothing, the collector records that default with `is_default: true`. This is what lets an
approved-registry guardrail catch the most common case — a project that was never pointed at the
internal registry in the first place — and it means the guardrail cannot be satisfied by deleting a
config file.

### Registry hosts, not credentials

Only the registry location is collected. Auth tokens in `.npmrc`, `settings.xml` or `nuget.config`
are never read or written to Component JSON.

### Configured, not resolved

This collector reports which registry a repository is *configured* to resolve from. It does not
verify where each installed package actually came from — a repository whose `.npmrc` points at an
internal registry can still have a `package-lock.json` full of packages `resolved` from
`registry.npmjs.org`, if the lockfile predates the config change. Lockfiles do record that per
package (npm and yarn `resolved` URLs, `Gemfile.lock` `remote:`), so per-dependency provenance is
a viable follow-up, but Maven, Gradle and NuGet lockfiles don't record a source repository, so it
cannot replace this config-level check.

### Not covered

Container image registries are collected by the [`docker`](../docker) collector and enforced by the
`container` guardrails' `allowed-registries` check. Helm chart repositories are collected by the
[`helm`](../helm) collector. Go resolves through the `GOPROXY` environment variable rather than a
committed file, and Cargo's `.cargo/config.toml` is not yet parsed.

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Description |
|--------|-------------|
| `scan` | Parses package-manager config and manifests, and records the resolved registries |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/package-registries@v1.0.0
    on: ["domain:your-domain"]  # Or use tags like [backend, node]
    # with:
    #   ecosystems: "npm,maven"   # Restrict to specific ecosystems
```

Pair it with the [`dependencies`](../../policies/dependencies) guardrails to enforce an approved
registry allowlist:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/dependencies@v1.0.0
    include: [approved-registries]
    on: ["domain:your-domain"]
    with:
      allowed_registries: "dl.cloudsmith.io"
```
