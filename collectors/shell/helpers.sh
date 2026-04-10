#!/bin/bash

is_shell_project() {
    local find_cmd="${LUNAR_INPUT_FIND_COMMAND:-find . -type f \( -name '*.sh' -o -name '*.bash' \) -not -path '*/node_modules/*' -not -path '*/vendor/*' -not -path '*/.git/*' -not -path '*/dist/*' -not -path '*/.terraform/*'}"
    if eval "$find_cmd" 2>/dev/null | head -1 | grep -q .; then
        return 0
    fi
    return 1
}

get_shell_scripts() {
    local find_cmd="${LUNAR_INPUT_FIND_COMMAND:-find . -type f \( -name '*.sh' -o -name '*.bash' \) -not -path '*/node_modules/*' -not -path '*/vendor/*' -not -path '*/.git/*' -not -path '*/dist/*' -not -path '*/.terraform/*'}"
    eval "$find_cmd" 2>/dev/null | sort
}
