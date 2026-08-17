# Category: `.dependencies`

Where a component resolves its dependencies from. **Normalized across npm, pip, Maven, Gradle,
RubyGems and NuGet.**

This category describes dependency *sourcing* — the registries a build resolves against. The
dependencies themselves live elsewhere: `.lang.<language>.dependencies` for language-native
inventory and `.sbom` for cross-language inventory with licenses. Container image registries are
`.containers`, not here.

```json
{
  "dependencies": {
    "source": {
      "tool": "package-registries",
      "integration": "code"
    },
    "ecosystems": ["npm", "maven"],
    "registries": [
      {
        "ecosystem": "npm",
        "host": "dl.cloudsmith.io",
        "url": "https://dl.cloudsmith.io/basic/acme/npm/",
        "path": ".npmrc",
        "kind": "primary",
        "is_default": false,
        "is_public": false
      },
      {
        "ecosystem": "maven",
        "host": "repo.maven.apache.org",
        "url": "https://repo.maven.apache.org/maven2",
        "path": "pom.xml",
        "name": "central",
        "kind": "primary",
        "is_default": true,
        "is_public": true
      }
    ],
    "registries_used": ["dl.cloudsmith.io", "repo.maven.apache.org"],
    "summary": {
      "has_public": true
    }
  }
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `ecosystems[]` | array | Package ecosystems detected in the repository |
| `registries[].ecosystem` | string | `npm`, `pip`, `maven`, `gradle`, `rubygems`, `nuget` |
| `registries[].host` | string | Registry hostname — what allowlists match against |
| `registries[].url` | string | Registry URL as declared, or the ecosystem default |
| `registries[].path` | string | File the declaration was read from |
| `registries[].name` | string | Declaration identifier where one exists (npm scope, Maven repo id) |
| `registries[].kind` | string | `primary`, `extra`, `mirror`, `plugin`, `publish` |
| `registries[].is_default` | boolean | `true` when nothing was declared and the ecosystem default applies |
| `registries[].is_public` | boolean | `true` when the host is a well-known public index |
| `registries_used[]` | array | Deduplicated hostnames across all ecosystems |
| `summary.has_public` | boolean | Any resolved registry is a public index |

## Implicit Defaults Are Recorded

A repository with a `package.json` but no `.npmrc` still resolves from `registry.npmjs.org`.
Collectors record that as an entry with `is_default: true` rather than omitting it, so an
approved-registry guardrail catches the common case of a project that was never pointed at the
internal registry. This mirrors how the `container` guardrails default a bare image reference to
`docker.io` before checking it.

Absence of the whole `.dependencies` object means no package ecosystem was detected — guardrails
should skip, not fail.

## Allowlists Live in Policy, Not Here

Collectors record which registries are configured; whether a registry is *approved* is policy
configuration (`allowed_registries`). Keeping the allowlist out of the Component JSON means one
collection serves consumers with different allowlists, and changing an allowlist re-evaluates
policy without waiting for re-collection.

## Key Policy Paths

- `.dependencies` — Package-manager config was analyzed (guardrails skip when absent)
- `.dependencies.registries[].host` — Host to match against an allowlist
- `.dependencies.registries[].is_public` — Resolving from a public index
- `.dependencies.summary.has_public` — Any public index in use
