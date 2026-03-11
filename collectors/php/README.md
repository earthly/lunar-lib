# PHP Collector

Collects PHP project information, CI/CD commands, dependencies, and tooling configuration.

## Overview

This collector gathers metadata about PHP projects including Composer configuration, dependency graphs, PHPUnit test setup, static analysis tools (PHPStan, Psalm), and code style tools (PHP-CS-Fixer, PHP_CodeSniffer). It runs on both code changes (for static analysis of project structure) and CI hooks (to capture runtime metrics).

**Note:** The CI-hook collector (`cicd`) doesn't run tests — it observes and collects data from `php` and `composer` commands that your CI pipeline already runs.

## Collected Data

This collector writes to the following Component JSON paths:

| Path | Type | Description |
|------|------|-------------|
| `.lang.php` | object | PHP project metadata (name, version constraint, build systems) |
| `.lang.php.composer_json_exists` | boolean | Whether composer.json is present |
| `.lang.php.composer_lock_exists` | boolean | Whether composer.lock is present |
| `.lang.php.phpunit_configured` | boolean | Whether PHPUnit is configured |
| `.lang.php.static_analysis_configured` | boolean | Whether PHPStan or Psalm is configured |
| `.lang.php.code_style_configured` | boolean | Whether PHP-CS-Fixer or PHP_CodeSniffer is configured |
| `.lang.php.dependencies` | object | Direct and dev dependencies from composer.json |
| `.lang.php.cicd` | object | CI/CD command tracking with PHP version |

## Collectors

This plugin provides the following collectors (use `include` to select a subset):

| Collector | Hook Type | Description |
|-----------|-----------|-------------|
| `project` | code | Collects PHP project structure (composer.json, lockfile, tooling) |
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
