#!/bin/bash

is_html_project() {
    # HTML files
    if find . -maxdepth 3 -type f -name "*.html" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi

    # CSS files
    if find . -maxdepth 3 -type f -name "*.css" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi

    # SCSS files
    if find . -maxdepth 3 -type f -name "*.scss" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi

    # LESS files
    if find . -maxdepth 3 -type f -name "*.less" -not -path './.git/*' -not -path '*/node_modules/*' 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi

    return 1
}
