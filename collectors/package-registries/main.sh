#!/bin/bash
# Record which package registries this repository resolves dependencies from.
#
# Reads package-manager configuration already committed to the repo. No registry
# credentials are needed, and none are collected.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Collector inputs arrive as LUNAR_VAR_<UPPER>. Defaults mirror the manifest so
# that a direct `lunar collector dev` run behaves the same as the hub.
DEFAULT_FIND="find . -type f \( -name '.npmrc' -o -name 'package.json' -o -name 'pip.conf' -o -name 'pip.ini' -o -name 'requirements*.txt' -o -name 'pyproject.toml' -o -name 'pom.xml' -o -name 'settings.xml' -o -name 'build.gradle' -o -name 'build.gradle.kts' -o -name 'settings.gradle' -o -name 'settings.gradle.kts' -o -name 'Gemfile' -o -name 'packages.config' -o -name '*.csproj' -o -iname 'nuget.config' \) -not -path '*/node_modules/*' -not -path '*/.git/*'"

FIND_COMMAND="${LUNAR_VAR_FIND_COMMAND:-$DEFAULT_FIND}"
# Empty is meaningful here (scan every ecosystem), so default only when unset.
ECOSYSTEMS="${LUNAR_VAR_ECOSYSTEMS-}"
export ECOSYSTEMS

if ! command -v python3 >/dev/null 2>&1; then
    echo "package-registries: python3 not found; skipping" >&2
    exit 0
fi

FILES=$(eval "$FIND_COMMAND" 2>/dev/null || true)

if [ -z "$FILES" ]; then
    echo "package-registries: no package-manager configuration found; nothing to collect" >&2
    exit 0
fi

RESULT=$(printf '%s\n' "$FILES" | python3 "$SCRIPT_DIR/parse_registries.py")

# No recognized ecosystem: write nothing so guardrails skip rather than fail.
if [ -z "$RESULT" ]; then
    echo "package-registries: no package ecosystem detected; nothing to collect" >&2
    exit 0
fi

printf '%s' "$RESULT" | lunar collect -j ".dependencies" -
