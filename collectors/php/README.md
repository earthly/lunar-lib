# PHP Collector

Collects PHP project information, CI/CD commands, and dependencies.

## Overview

This collector gathers metadata about PHP projects including Composer configuration, dependency graphs, tool configuration (PHPUnit, PHPStan, Psalm, PHP-CS-Fixer, PHP_CodeSniffer), and CI/CD command tracking. It runs on both code changes (for static analysis) and CI hooks (to capture runtime metrics).

**Note:** The CI-hook collector (`cicd`) doesn't run PHP commands — it observes and collects data from `php` and `composer` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.php` | object | PHP project metadata (version, build systems, tool config) |
| `.lang.php.version` | string | PHP version constraint from composer.json |
| `.lang.php.cicd` | object | CI/CD command tracking with PHP version |
| `.lang.php.dependencies` | object | Direct and dev dependencies from composer.json |

## Collectors

This integration provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects PHP project structure (composer.json, composer.lock, vendor, tool config) |
| `dependencies` | code | Collects Composer dependency graph |
| `cicd` | ci-before-command | Tracks PHP/Composer commands run in CI with version info |

## Installation

Add to your `lunar-config.yml`:

```yaml
collectors:
  - uses: github://earthly/lunar-lib/collectors/php@v1.0.0
    on: [php]  # Or use domain: ["domain:your-domain"]
    # include: [project, dependencies]  # Only include specific subcollectors
```
