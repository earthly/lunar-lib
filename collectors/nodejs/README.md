# Node.js Collector

Collects Node.js project information, CI/CD commands, test coverage, and dependencies.

## Overview

This collector gathers metadata about Node.js projects including package manager detection, dependency graphs, TypeScript and linter configuration, monorepo setup, and test coverage metrics. It runs on both code changes (for static analysis) and CI hooks (to capture runtime metrics like test coverage and command tracking).

**Note:** The CI-hook collectors (`test-coverage`, `cicd`, `npm-cicd`, `yarn-cicd`, `pnpm-cicd`) don't run tests—they observe and collect data from commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.nodejs` | object | Node.js project metadata (version, build systems) |
| `.lang.nodejs.dependencies` | object | Direct and dev dependencies from package.json |
| `.lang.nodejs.cicd` | object | Node.js runtime CI/CD command tracking with version |
| `.lang.nodejs.npm.cicd` | object | npm CI/CD command tracking with version |
| `.lang.nodejs.yarn.cicd` | object | Yarn CI/CD command tracking with version |
| `.lang.nodejs.pnpm.cicd` | object | pnpm CI/CD command tracking with version |
| `.lang.nodejs.tests.coverage` | object | Test coverage percentage and source |
| `.testing.coverage` | object | Normalized cross-language coverage (dual-write) |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects project structure (package.json, lockfiles, TypeScript, ESLint, monorepo) |
| `dependencies` | code | Collects dependencies from package.json |
| `cicd` | ci-before-command | Tracks node commands run in CI with Node.js runtime version |
| `npm-cicd` | ci-before-command | Tracks npm/npx commands run in CI with npm version |
| `yarn-cicd` | ci-before-command | Tracks Yarn commands run in CI with Yarn version |
| `pnpm-cicd` | ci-before-command | Tracks pnpm commands run in CI with pnpm version |
| `test-coverage` | ci-after-command | Extracts coverage from existing test output |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/nodejs@v1.0.0
    on: ["domain:your-domain"]  # replace with your own domain or tags
    # include: [project, dependencies]  # Only include specific subcollectors
```
