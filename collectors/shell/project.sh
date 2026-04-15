#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_shell_project; then
    echo "No shell scripts detected" >&2
    exit 0
fi

# Collect all shell script paths
scripts=()
while IFS= read -r f; do
    [[ -n "$f" ]] && scripts+=("$f")
done < <(get_shell_scripts)

script_count=${#scripts[@]}
if [[ "$script_count" -eq 0 ]]; then
    echo "No shell scripts found" >&2
    exit 0
fi

# Build scripts JSON array
scripts_json=$(printf '%s\n' "${scripts[@]}" | jq -R . | jq -s .)

# Detect shell types from shebang lines
shells_set=()
for f in "${scripts[@]}"; do
    if [[ -f "$f" ]]; then
        shebang=$(head -1 "$f" 2>/dev/null || true)
        case "$shebang" in
            *bash*)  shells_set+=("bash") ;;
            *zsh*)   shells_set+=("zsh") ;;
            *dash*)  shells_set+=("dash") ;;
            *ksh*)   shells_set+=("ksh") ;;
            *fish*)  shells_set+=("fish") ;;
            *sh*)    shells_set+=("sh") ;;
            *)
                # No shebang — infer from extension
                case "$f" in
                    *.bash) shells_set+=("bash") ;;
                    *.sh)   shells_set+=("sh") ;;
                esac
                ;;
        esac
    fi
done

# Deduplicate shells
shells_json=$(printf '%s\n' "${shells_set[@]}" | sort -u | jq -R . | jq -s .)

# Collect project data
jq -n \
    --argjson script_count "$script_count" \
    --argjson scripts "$scripts_json" \
    --argjson shells "$shells_json" \
    '{
        script_count: $script_count,
        scripts: $scripts,
        shells: $shells,
        source: { tool: "shell-collector", integration: "code" }
    }' | lunar collect -j ".lang.shell" -
