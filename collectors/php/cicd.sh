#!/bin/bash
set -e

# Record PHP/Composer commands executed in CI
# LUNAR_CI_COMMAND contains the full command being observed.

cmd="${LUNAR_CI_COMMAND:-}"
if [[ -z "$cmd" ]]; then
    echo "No CI command captured, exiting"
    exit 0
fi

# Get PHP version
php_version=$(php -v 2>/dev/null | head -1 | awk '{print $2}' || echo "")

jq -n \
    --arg cmd "$cmd" \
    --arg version "$php_version" \
    '[{cmd: $cmd, version: $version}]' | lunar collect -j ".lang.php.cicd.cmds" --append -
