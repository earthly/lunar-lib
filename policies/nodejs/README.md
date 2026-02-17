# Node.js Project Guardrails

Enforce Node.js-specific project standards including lockfile presence, TypeScript configuration, engine version pinning, and minimum Node.js version requirements.

## Overview

This policy validates Node.js projects against best practices for package management and project structure. It ensures projects have lockfiles for reproducible builds, TypeScript for type safety, pinned engine versions, and meet minimum Node.js version requirements in both code and CI environments.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description |
|--------|-------------|
| `lockfile-exists` | Validates a lockfile exists (package-lock.json, yarn.lock, or pnpm-lock.yaml) |
| `typescript-configured` | Validates tsconfig.json exists |
| `engines-pinned` | Ensures engines.node is set in package.json |
| `min-node-version` | Ensures minimum Node.js version |
| `min-node-version-cicd` | Ensures minimum Node.js version in CI/CD |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.nodejs` | object | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.native.package_lock.exists` | boolean | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.native.yarn_lock.exists` | boolean | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.native.pnpm_lock.exists` | boolean | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.native.tsconfig.exists` | boolean | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.native.engines_node` | string | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.version` | string | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |
| `.lang.nodejs.cicd.cmds` | array | [`nodejs`](https://github.com/earthly/lunar-lib/tree/main/collectors/nodejs) collector |

**Note:** Ensure the corresponding collector(s) are configured before enabling this policy.

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/nodejs@v1.0.0
    on: [nodejs]  # Or use tags like ["domain:frontend"]
    enforcement: report-pr
    # include: [lockfile-exists, typescript-configured]  # Only run specific checks
    with:
      min_node_version: "18"       # Minimum required Node.js major version (default: "18")
      min_node_version_cicd: "18"  # Minimum Node.js version for CI/CD commands (default: "18")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "nodejs": {
      "version": "20.11.0",
      "native": {
        "package_lock": { "exists": true },
        "tsconfig": { "exists": true },
        "engines_node": ">=18"
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "nodejs": {
      "version": "16.20.0",
      "native": {
        "package_lock": { "exists": false },
        "yarn_lock": { "exists": false },
        "pnpm_lock": { "exists": false },
        "tsconfig": { "exists": false }
      }
    }
  }
}
```

**Failure messages:**
- `"No lockfile found. Run 'npm install', 'yarn install', or 'pnpm install' to generate a lockfile and commit it to version control."`
- `"TypeScript is not configured. Add a tsconfig.json to enable type checking."`
- `"engines.node is not set in package.json."`
- `"Node.js version 16.20.0 is below minimum 18."`

## Remediation

When this policy fails, you can resolve it by:

1. **lockfile-exists**: Run `npm install`, `yarn install`, or `pnpm install` to generate a lockfile and commit it to version control.
2. **typescript-configured**: Run `npx tsc --init` to generate a tsconfig.json and configure compiler options.
3. **engines-pinned**: Add `"engines": { "node": ">=18" }` to package.json to communicate the required version.
4. **min-node-version**: Update your project's Node.js version and `.nvmrc`, `.node-version`, or `engines.node`.
5. **min-node-version-cicd**: Update your CI/CD pipeline (GitHub Actions `node-version` or Docker base image).
