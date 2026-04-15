#!/bin/bash
set -e

source "$(dirname "$0")/helpers.sh"

if ! is_ruby_project; then
    echo "No Ruby project detected, skipping" >&2
    exit 0
fi

# Detect project files
gemfile_exists=false
[[ -f "Gemfile" ]] && gemfile_exists=true

gemfile_lock_exists=false
[[ -f "Gemfile.lock" ]] && gemfile_lock_exists=true

ruby_version_file_exists=false
[[ -f ".ruby-version" ]] && ruby_version_file_exists=true

rakefile_exists=false
[[ -f "Rakefile" ]] && rakefile_exists=true

# Find gemspec files
gemspec_json="[]"
gemspec_files=$(find . -maxdepth 2 -name "*.gemspec" -type f 2>/dev/null | sed 's|^\./||')
if [[ -n "$gemspec_files" ]]; then
    gemspec_json=$(echo "$gemspec_files" | jq -R . | jq -s .)
fi

# Detect build systems
systems=""
if [[ "$gemfile_exists" == "true" ]]; then
    systems="${systems:+$systems,}\"bundler\""
fi
if [[ "$rakefile_exists" == "true" ]]; then
    systems="${systems:+$systems,}\"rake\""
fi
build_systems="[${systems}]"

# Extract Ruby version
ruby_version=""

# 1. Try .ruby-version file
if [[ -f ".ruby-version" ]]; then
    ruby_version=$(head -1 .ruby-version | sed 's/^ruby-//' | tr -d '[:space:]')
fi

# 2. Fall back to Gemfile ruby directive
if [[ -z "$ruby_version" && -f "Gemfile" ]]; then
    ruby_version=$(sed -n "s/^ruby[[:space:]]*['\"]\\([^'\"]*\\)['\"].*/\\1/p" Gemfile | head -1)
fi

# 3. Fall back to Gemfile.lock RUBY VERSION section
if [[ -z "$ruby_version" && -f "Gemfile.lock" ]]; then
    ruby_version=$(sed -n '/^RUBY VERSION$/,/^$/{s/^[[:space:]]*ruby \([0-9][0-9.]*\).*/\1/p;}' Gemfile.lock | head -1)
fi

# Build JSON and collect
jq -n \
    --argjson gemfile_exists "$gemfile_exists" \
    --argjson gemfile_lock_exists "$gemfile_lock_exists" \
    --argjson ruby_version_file_exists "$ruby_version_file_exists" \
    --argjson rakefile_exists "$rakefile_exists" \
    --argjson gemspec_files "$gemspec_json" \
    --argjson build_systems "$build_systems" \
    --arg version "$ruby_version" \
    '{
        gemfile_exists: $gemfile_exists,
        gemfile_lock_exists: $gemfile_lock_exists,
        ruby_version_file_exists: $ruby_version_file_exists,
        rakefile_exists: $rakefile_exists,
        gemspec_files: $gemspec_files,
        build_systems: $build_systems,
        version: $version,
        source: {
            tool: "ruby",
            integration: "code"
        }
    }' | lunar collect -j ".lang.ruby" -
