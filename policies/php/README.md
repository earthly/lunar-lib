# PHP Project Guardrails

Enforce PHP-specific project standards including Composer configuration, lockfile presence, testing setup, static analysis, and code style enforcement.

## Overview

This policy validates PHP projects against best practices for dependency management and project structure. It ensures projects have proper `composer.json` and `composer.lock` files, configure PHPUnit for testing, use a static analysis tool like PHPStan or Psalm, enforce consistent code style with PHP-CS-Fixer or PHP_CodeSniffer, and meet minimum PHP version requirements.

## Policies

This plugin provides the following policies (use `include` to select a subset):

| Policy | Description | Failure Meaning |
|--------|-------------|-----------------|
| `composer-json-exists` | Validates composer.json exists | Project lacks dependency definition |
| `composer-lock-exists` | Validates composer.lock exists | Missing dependency lockfile |
| `phpunit-configured` | Ensures PHPUnit is configured | No test framework set up |
| `static-analysis-configured` | Ensures PHPStan or Psalm is configured | No static analysis tool |
| `code-style-configured` | Ensures PHP-CS-Fixer or PHP_CodeSniffer is configured | No code style enforcement |
| `min-php-version` | Ensures minimum PHP version constraint | PHP version too old |

## Required Data

This policy reads from the following Component JSON paths:

| Path | Type | Provided By |
|------|------|-------------|
| `.lang.php` | object | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.composer_json_exists` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.composer_lock_exists` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.phpunit_configured` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.static_analysis_configured` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.code_style_configured` | boolean | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |
| `.lang.php.version` | string | [`php`](https://github.com/earthly/lunar-lib/tree/main/collectors/php) collector |

## Installation

Add to your `lunar-config.yml`:

```yaml
policies:
  - uses: github://earthly/lunar-lib/policies/php@v1.0.0
    on: [php]  # Or use tags like ["domain:backend"]
    enforcement: report-pr
    # include: [composer-json-exists, composer-lock-exists]  # Only run specific checks
    with:
      min_php_version: "8.1"  # Minimum required PHP version (default: "8.1")
```

## Examples

### Passing Example

```json
{
  "lang": {
    "php": {
      "name": "acme/my-project",
      "php_version": "^8.2",
      "composer_json_exists": true,
      "composer_lock_exists": true,
      "phpunit_configured": true,
      "static_analysis_configured": true,
      "code_style_configured": true
    }
  }
}
```

### Failing Example

```json
{
  "lang": {
    "php": {
      "php_version": "^7.4",
      "composer_json_exists": true,
      "composer_lock_exists": false,
      "phpunit_configured": false,
      "static_analysis_configured": false,
      "code_style_configured": false
    }
  }
}
```

**Failure messages:**
- `"composer.lock not found. Run 'composer install' or 'composer update' to generate it and commit it to version control."`
- `"PHPUnit is not configured. Create a phpunit.xml or phpunit.xml.dist file and add phpunit/phpunit to require-dev in composer.json."`
- `"No static analysis tool configured. Set up PHPStan (phpstan.neon) or Psalm (psalm.xml)."`
- `"PHP version constraint '^7.4' allows versions below minimum 8.1."`

## Remediation

### composer-json-exists
1. Run `composer init` to create a composer.json file
2. Define your project dependencies and metadata

### composer-lock-exists
1. Run `composer install` or `composer update` to generate composer.lock
2. Commit the composer.lock file to version control
3. Never add composer.lock to .gitignore for application projects

### phpunit-configured
1. Install PHPUnit: `composer require --dev phpunit/phpunit`
2. Create a `phpunit.xml.dist` configuration file in the project root
3. Define your test suite directories and bootstrap file

### static-analysis-configured
1. Install PHPStan: `composer require --dev phpstan/phpstan` and create `phpstan.neon`
2. Or install Psalm: `composer require --dev vimeo/psalm` and run `./vendor/bin/psalm --init`
3. Configure the appropriate level for your project

### code-style-configured
1. Install PHP-CS-Fixer: `composer require --dev friendsofphp/php-cs-fixer` and create `.php-cs-fixer.php`
2. Or install PHP_CodeSniffer: `composer require --dev squizlabs/php_codesniffer` and create `phpcs.xml`
3. Configure PSR-12 or your preferred coding standard

### min-php-version
1. Update the `require.php` field in composer.json: `"php": "^8.1"`
2. Run `composer update` to verify compatibility
3. Test your code with the new PHP version
