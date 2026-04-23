#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_elixir_project; then
    echo "No Elixir project detected, exiting"
    exit 0
fi

mix_exs_exists=false
mix_lock_exists=false
test_directory_exists=false
credo_configured=false
dialyzer_configured=false
formatter_configured=false
project_name=""
project_version=""
elixir_requirement=""

[[ -f "mix.exs" ]] && mix_exs_exists=true
[[ -f "mix.lock" ]] && mix_lock_exists=true
[[ -d "test" ]] && test_directory_exists=true
[[ -f ".credo.exs" ]] && credo_configured=true
[[ -f ".formatter.exs" ]] && formatter_configured=true

if [[ "$mix_exs_exists" == "true" ]]; then
    # app: :my_app — may appear after `[` or whitespace, so don't anchor to line start
    project_name=$(sed -n 's/.*[^a-zA-Z0-9_]app:[[:space:]]*:\([a-zA-Z0-9_]*\).*/\1/p' mix.exs | head -1)

    # version: "0.1.0"
    project_version=$(extract_mix_string mix.exs version)

    # elixir: "~> 1.15"
    elixir_requirement=$(extract_mix_string mix.exs elixir)

    # Dialyzer: :dialyxir dep or dialyzer/0 / dialyzer: [ ... ] block
    if grep -q ':dialyxir' mix.exs 2>/dev/null; then
        dialyzer_configured=true
    elif grep -qE '^[[:space:]]*(defp?[[:space:]]+dialyzer|dialyzer:)' mix.exs 2>/dev/null; then
        dialyzer_configured=true
    fi
fi

# OTP apps: for a flat project this is just [project_name]; for an umbrella
# it's populated further down after walking apps/*/mix.exs.
otp_apps_json="[]"
if [[ -n "$project_name" ]]; then
    otp_apps_json=$(jq -n --arg app "$project_name" '[$app]')
fi

# Umbrella: apps_path: "apps" in mix.exs. Walk apps/*/mix.exs to collect
# umbrella member app atoms (from each child's `app:` key in project/0).
umbrella_json='{"is_umbrella": false}'
if [[ "$mix_exs_exists" == "true" ]]; then
    if grep -q 'apps_path:' mix.exs 2>/dev/null; then
        apps_list_json="[]"
        if [[ -d "apps" ]]; then
            while IFS= read -r child_mix; do
                [[ -z "$child_mix" ]] && continue
                child_app=$(sed -n 's/.*[^a-zA-Z0-9_]app:[[:space:]]*:\([a-zA-Z0-9_]*\).*/\1/p' "$child_mix" | head -1)
                [[ -n "$child_app" ]] && apps_list_json=$(jq --arg a "$child_app" '. + [$a]' <<<"$apps_list_json")
            done < <(find apps -mindepth 2 -maxdepth 2 -name mix.exs 2>/dev/null)
        fi
        umbrella_json=$(jq -n --argjson apps "$apps_list_json" '{is_umbrella: true, apps: $apps}')
        # For umbrella projects, otp_apps reflects the child app atoms
        otp_apps_json="$apps_list_json"
    fi
fi

# Framework detection from deps/0 list in mix.exs.
# Maps hex dep names to canonical framework labels.
frameworks_json="[]"
if [[ "$mix_exs_exists" == "true" ]]; then
    declare -a frameworks=()
    if grep -qE '\{:phoenix,' mix.exs 2>/dev/null; then
        frameworks+=("phoenix")
    fi
    if grep -qE '\{:phoenix_live_view,' mix.exs 2>/dev/null; then
        frameworks+=("phoenix_live_view")
    fi
    if grep -qE '\{:(ecto|ecto_sql),' mix.exs 2>/dev/null; then
        frameworks+=("ecto")
    fi
    if [[ ${#frameworks[@]} -gt 0 ]]; then
        frameworks_json=$(printf '%s\n' "${frameworks[@]}" | jq -R . | jq -s 'unique')
    fi
fi

# Elixir + OTP runtime versions from the container.
elixir_version=$(elixir --version 2>/dev/null | sed -n 's/^Elixir[[:space:]]\([0-9.]*\).*/\1/p' | head -1)
otp_version=$(elixir --version 2>/dev/null | sed -n 's/.*Erlang\/OTP[[:space:]]\([0-9]*\).*/\1/p' | head -1)

jq -n \
    --arg project_name "$project_name" \
    --arg project_version "$project_version" \
    --arg elixir_requirement "$elixir_requirement" \
    --arg elixir_version "$elixir_version" \
    --arg otp_version "$otp_version" \
    --argjson mix_exs_exists "$mix_exs_exists" \
    --argjson mix_lock_exists "$mix_lock_exists" \
    --argjson test_directory_exists "$test_directory_exists" \
    --argjson credo_configured "$credo_configured" \
    --argjson dialyzer_configured "$dialyzer_configured" \
    --argjson formatter_configured "$formatter_configured" \
    --argjson otp_apps "$otp_apps_json" \
    --argjson umbrella "$umbrella_json" \
    --argjson frameworks "$frameworks_json" \
    '{
        build_systems: ["mix"],
        mix_exs_exists: $mix_exs_exists,
        mix_lock_exists: $mix_lock_exists,
        test_directory_exists: $test_directory_exists,
        credo_configured: $credo_configured,
        dialyzer_configured: $dialyzer_configured,
        formatter_configured: $formatter_configured,
        otp_apps: $otp_apps,
        umbrella: $umbrella,
        frameworks: $frameworks,
        source: {
            tool: "mix",
            integration: "code"
        }
    }
    | if $project_name != "" then .project_name = $project_name else . end
    | if $project_version != "" then .project_version = $project_version else . end
    | if $elixir_requirement != "" then .elixir_requirement = $elixir_requirement else . end
    | if $elixir_version != "" then .version = $elixir_version else . end
    | if $otp_version != "" then .otp_version = $otp_version else . end' |
    lunar collect -j ".lang.elixir" -
