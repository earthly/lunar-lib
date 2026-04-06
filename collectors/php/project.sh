#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

# Check if this is a PHP project
if ! is_php_project; then
    echo "No PHP project detected, exiting"
    exit 0
fi

composer_json_exists=false
composer_lock_exists=false
vendor_exists=false
phpunit_configured=false
static_analysis_configured=false
static_analysis_tool=""
code_style_configured=false
code_style_tool=""
php_version=""

# Check for composer.json
if [[ -f "composer.json" ]]; then
    composer_json_exists=true

    # Extract PHP version constraint from require.php
    php_version=$(jq -r '.require.php // ""' composer.json 2>/dev/null || echo "")
fi

# Check for composer.lock
[[ -f "composer.lock" ]] && composer_lock_exists=true

# Check for vendor directory
[[ -d "vendor" ]] && vendor_exists=true

# Check for PHPUnit configuration
if [[ -f "phpunit.xml" ]] || [[ -f "phpunit.xml.dist" ]] || [[ -f "phpunit.dist.xml" ]]; then
    phpunit_configured=true
elif [[ "$composer_json_exists" == true ]] && jq -e '.["require-dev"]["phpunit/phpunit"] // empty' composer.json >/dev/null 2>&1; then
    phpunit_configured=true
fi

# Check for static analysis tools (PHPStan or Psalm)
if [[ -f "phpstan.neon" ]] || [[ -f "phpstan.neon.dist" ]] || [[ -f "phpstan.dist.neon" ]]; then
    static_analysis_configured=true
    static_analysis_tool="phpstan"
elif [[ -f "psalm.xml" ]] || [[ -f "psalm.xml.dist" ]]; then
    static_analysis_configured=true
    static_analysis_tool="psalm"
elif [[ "$composer_json_exists" == true ]]; then
    if jq -e '.["require-dev"]["phpstan/phpstan"] // empty' composer.json >/dev/null 2>&1; then
        static_analysis_configured=true
        static_analysis_tool="phpstan"
    elif jq -e '.["require-dev"]["vimeo/psalm"] // empty' composer.json >/dev/null 2>&1; then
        static_analysis_configured=true
        static_analysis_tool="psalm"
    fi
fi

# Check for code style tools (PHP-CS-Fixer or PHP_CodeSniffer)
if [[ -f ".php-cs-fixer.php" ]] || [[ -f ".php-cs-fixer.dist.php" ]] || [[ -f ".php_cs" ]] || [[ -f ".php_cs.dist" ]]; then
    code_style_configured=true
    code_style_tool="php-cs-fixer"
elif [[ -f "phpcs.xml" ]] || [[ -f "phpcs.xml.dist" ]] || [[ -f ".phpcs.xml" ]] || [[ -f ".phpcs.xml.dist" ]]; then
    code_style_configured=true
    code_style_tool="phpcs"
elif [[ "$composer_json_exists" == true ]]; then
    if jq -e '.["require-dev"]["friendsofphp/php-cs-fixer"] // empty' composer.json >/dev/null 2>&1; then
        code_style_configured=true
        code_style_tool="php-cs-fixer"
    elif jq -e '.["require-dev"]["squizlabs/php_codesniffer"] // empty' composer.json >/dev/null 2>&1; then
        code_style_configured=true
        code_style_tool="phpcs"
    fi
fi

# Build and collect — flat booleans at .lang.php level plus composer metadata nested
jq -n \
    --arg version "$php_version" \
    --argjson phpunit_configured "$phpunit_configured" \
    --argjson static_analysis_configured "$static_analysis_configured" \
    --arg static_analysis_tool "$static_analysis_tool" \
    --argjson code_style_configured "$code_style_configured" \
    --arg code_style_tool "$code_style_tool" \
    --argjson composer_json_exists "$composer_json_exists" \
    --argjson composer_lock_exists "$composer_lock_exists" \
    --argjson vendor_exists "$vendor_exists" \
    '{
        project_exists: $composer_json_exists,
        build_systems: ["composer"],
        phpunit_configured: $phpunit_configured,
        static_analysis_configured: $static_analysis_configured,
        static_analysis_tool: (if $static_analysis_tool != "" then $static_analysis_tool else null end),
        code_style_configured: $code_style_configured,
        code_style_tool: (if $code_style_tool != "" then $code_style_tool else null end),
        composer: {
            json_exists: $composer_json_exists,
            lock_exists: $composer_lock_exists,
            vendor_exists: $vendor_exists
        },
        source: {
            tool: "php",
            integration: "code"
        }
    }
    | if $version != "" then .version = $version else . end' | lunar collect -j ".lang.php" -
