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
phpstan_configured=false
psalm_configured=false
php_cs_fixer_configured=false
phpcs_configured=false
php_version=""
project_name=""

# Check for composer.json
if [[ -f "composer.json" ]]; then
    composer_json_exists=true
    project_name=$(jq -r '.name // ""' composer.json 2>/dev/null || echo "")
    php_version=$(jq -r '.require.php // ""' composer.json 2>/dev/null || echo "")
fi

# Check for composer.lock
[[ -f "composer.lock" ]] && composer_lock_exists=true

# Check for vendor directory
[[ -d "vendor" ]] && vendor_exists=true

# Detect PHPUnit configuration
if [[ -f "phpunit.xml" ]] || [[ -f "phpunit.xml.dist" ]] || [[ -f "phpunit.dist.xml" ]]; then
    phpunit_configured=true
fi

# Detect PHPStan configuration
if [[ -f "phpstan.neon" ]] || [[ -f "phpstan.neon.dist" ]] || [[ -f "phpstan.dist.neon" ]]; then
    phpstan_configured=true
elif [[ "$composer_json_exists" == true ]] && jq -e '.require-dev["phpstan/phpstan"] // .require["phpstan/phpstan"]' composer.json > /dev/null 2>&1; then
    phpstan_configured=true
fi

# Detect Psalm configuration
if [[ -f "psalm.xml" ]] || [[ -f "psalm.xml.dist" ]]; then
    psalm_configured=true
elif [[ "$composer_json_exists" == true ]] && jq -e '.require-dev["vimeo/psalm"] // .require["vimeo/psalm"]' composer.json > /dev/null 2>&1; then
    psalm_configured=true
fi

# Detect PHP-CS-Fixer configuration
if [[ -f ".php-cs-fixer.php" ]] || [[ -f ".php-cs-fixer.dist.php" ]] || [[ -f ".php_cs" ]] || [[ -f ".php_cs.dist" ]]; then
    php_cs_fixer_configured=true
elif [[ "$composer_json_exists" == true ]] && jq -e '.require-dev["friendsofphp/php-cs-fixer"]' composer.json > /dev/null 2>&1; then
    php_cs_fixer_configured=true
fi

# Detect PHP_CodeSniffer configuration
if [[ -f "phpcs.xml" ]] || [[ -f "phpcs.xml.dist" ]] || [[ -f ".phpcs.xml" ]] || [[ -f ".phpcs.xml.dist" ]]; then
    phpcs_configured=true
elif [[ "$composer_json_exists" == true ]] && jq -e '.require-dev["squizlabs/php_codesniffer"]' composer.json > /dev/null 2>&1; then
    phpcs_configured=true
fi

# Determine build systems
build_systems=()
if [[ "$composer_json_exists" == true ]]; then
    build_systems+=("composer")
fi
if [[ ${#build_systems[@]} -eq 0 ]]; then
    build_systems=("composer")
fi

# Detect static analysis tool
static_analysis_configured=false
static_analysis=""
if [[ "$phpstan_configured" == true ]]; then
    static_analysis="phpstan"
    static_analysis_configured=true
elif [[ "$psalm_configured" == true ]]; then
    static_analysis="psalm"
    static_analysis_configured=true
fi

# Detect code style tool
code_style_configured=false
code_style=""
if [[ "$php_cs_fixer_configured" == true ]]; then
    code_style="php-cs-fixer"
    code_style_configured=true
elif [[ "$phpcs_configured" == true ]]; then
    code_style="phpcs"
    code_style_configured=true
fi

# Build and collect
jq -n \
    --argjson build_systems "$(printf '%s\n' "${build_systems[@]}" | jq -R . | jq -s .)" \
    --argjson composer_json_exists "$composer_json_exists" \
    --argjson composer_lock_exists "$composer_lock_exists" \
    --argjson vendor_exists "$vendor_exists" \
    --argjson phpunit_configured "$phpunit_configured" \
    --argjson static_analysis_configured "$static_analysis_configured" \
    --arg static_analysis "$static_analysis" \
    --argjson code_style_configured "$code_style_configured" \
    --arg code_style "$code_style" \
    --arg name "$project_name" \
    --arg php_version "$php_version" \
    '{
        build_systems: $build_systems,
        composer_json_exists: $composer_json_exists,
        composer_lock_exists: $composer_lock_exists,
        vendor_exists: $vendor_exists,
        phpunit_configured: $phpunit_configured,
        static_analysis_configured: $static_analysis_configured,
        static_analysis: (if $static_analysis != "" then $static_analysis else null end),
        code_style_configured: $code_style_configured,
        code_style: (if $code_style != "" then $code_style else null end),
        source: {
            tool: "php",
            integration: "code"
        }
    }
    | if $name != "" then .name = $name else . end
    | if $php_version != "" then .php_version = $php_version else . end' | lunar collect -j ".lang.php" -
