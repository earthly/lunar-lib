#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_html_project; then
    echo "No HTML/CSS project detected" >&2
    exit 0
fi

# Count files per type (exclude .git and node_modules)
html_count=$(find . -maxdepth 10 -type f -name "*.html" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | wc -l)
css_count=$(find . -maxdepth 10 -type f -name "*.css" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | wc -l)
scss_count=$(find . -maxdepth 10 -type f -name "*.scss" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | wc -l)
less_count=$(find . -maxdepth 10 -type f -name "*.less" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | wc -l)

# Write .lang.html if HTML files found
if [[ "$html_count" -gt 0 ]]; then
    jq -n \
        --argjson file_count "$html_count" \
        '{
            file_count: $file_count,
            source: { tool: "html", integration: "code" }
        }' | lunar collect -j ".lang.html" -
fi

# Write .lang.css if CSS files found
if [[ "$css_count" -gt 0 ]]; then
    jq -n \
        --argjson file_count "$css_count" \
        '{
            file_count: $file_count,
            source: { tool: "html", integration: "code" }
        }' | lunar collect -j ".lang.css" -
fi

# Write .lang.scss if SCSS files found
if [[ "$scss_count" -gt 0 ]]; then
    jq -n \
        --argjson file_count "$scss_count" \
        '{
            file_count: $file_count,
            source: { tool: "html", integration: "code" }
        }' | lunar collect -j ".lang.scss" -
fi

# Write .lang.less if LESS files found
if [[ "$less_count" -gt 0 ]]; then
    jq -n \
        --argjson file_count "$less_count" \
        '{
            file_count: $file_count,
            source: { tool: "html", integration: "code" }
        }' | lunar collect -j ".lang.less" -
fi
