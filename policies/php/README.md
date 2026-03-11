# PHP Project Guardrails

Enforce PHP-specific project standards including Composer configuration, tool setup, and PHP version requirements.

## Overview

This policy validates PHP projects against best practices for dependency management and project structure. It ensures projects have proper `composer.json` and `composer.lock` files, use a minimum PHP version, and have testing, static analysis, and code style tools configured.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `composer-json-exists` | Validates composer.json exists | Project lacks Composer dependency management |
| `composer-lock-exists` | Validates composer.lock exists | Missing lockfile for reproducible builds |
| `phpunit-configured` | Ensures PHPUnit is configured | No test framework detected |
| `static-analysis-configured` | Ensures PHPStan or Psalm is configured | No static analysis tool detected |
| `code-style-configured` | Ensures PHP-CS-Fixer or PHPCS is configured | No code style tool detected |
| `min-version` | Ensures minimum PHP version in composer.json | PHP version too old |
| `min-composer-version` | Ensures minimum Composer version in CI | Composer version too old |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.php` | object | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.version` | string | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.phpunit_configured` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.static_analysis_configured` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.code_style_configured` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.composer.json_exists` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.composer.lock_exists` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.composer.cicd` | object | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/php@v1.0.0
    on: [php]  # Or use tags like ["domain:backend"]
    enforcement: report-pr
    # include: [composer-json-exists, composer-lock-exists]  # Only run specific checks
    with:
      min_version: "8.1"  # Minimum required PHP version (default: "8.1")
      min_composer_version: "2.6"  # Minimum required Composer version (default: "2.6")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "php": {
      "version": "^8.2",
      "phpunit_configured": true,
      "static_analysis_configured": true,
      "code_style_configured": true,
      "composer": {
        "json_exists": true,
        "lock_exists": true
      }
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "php": {
      "version": "^7.4",
      "phpunit_configured": false,
      "static_analysis_configured": false,
      "code_style_configured": false,
      "composer": {
        "json_exists": true,
        "lock_exists": false
      }
    }
  }
}
```

**Failure messages:**
- `"composer.lock not found. Run 'composer install' to generate a lockfile for reproducible builds."`
- `"PHPUnit not configured. Add phpunit/phpunit to require-dev and create phpunit.xml."`
- `"No static analysis tool configured. Add PHPStan or Psalm to your project."`
- `"No code style tool configured. Add PHP-CS-Fixer or PHP_CodeSniffer to your project."`
- `"PHP version 7.4 is below minimum 8.1. Update the PHP constraint in composer.json."`
- `"Composer version 2.4.1 is below minimum 2.6. Update Composer in your CI pipeline."`

## Remediation

### composer-json-exists
1. Run `composer init` to create a composer.json file
2. Add your project dependencies with `composer require`

### composer-lock-exists
1. Run `composer install` to generate composer.lock
2. Commit the composer.lock file to version control

### phpunit-configured
1. Run `composer require --dev phpunit/phpunit`
2. Create a `phpunit.xml` or `phpunit.xml.dist` configuration file
3. Add a test script to composer.json: `"scripts": {"test": "phpunit"}`

### static-analysis-configured
1. Choose PHPStan or Psalm:
   - PHPStan: `composer require --dev phpstan/phpstan` and create `phpstan.neon`
   - Psalm: `composer require --dev vimeo/psalm` and run `vendor/bin/psalm --init`
2. Add to your CI pipeline for automated checking

### code-style-configured
1. Choose PHP-CS-Fixer or PHP_CodeSniffer:
   - PHP-CS-Fixer: `composer require --dev friendsofphp/php-cs-fixer` and create `.php-cs-fixer.php`
   - PHPCS: `composer require --dev squizlabs/php_codesniffer` and create `phpcs.xml`
2. Add to your CI pipeline for automated checking

### min-version
1. Update the `require.php` constraint in composer.json: `"php": ">=8.1"`
2. Run `composer update` to verify compatibility
3. Test your code with the new PHP version

### min-composer-version
1. Update Composer in your CI pipeline: `composer self-update`
2. Pin a minimum version in your CI config (e.g., `composer self-update --2.6`)
3. Consider using the official Composer Docker image with a specific version tag
