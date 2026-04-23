#!/bin/bash

# Shared helper functions for the elixir collector

# Check if the repo contains an Elixir project (root or subdirs).
# Requires mix.exs — stray .ex/.exs files alone are not sufficient,
# since downstream scripts need a mix manifest to parse.
is_elixir_project() {
    [[ -f "mix.exs" ]] && return 0
    git ls-files --error-unmatch '**/mix.exs' >/dev/null 2>&1
}

# Extract a single-quoted or double-quoted value from `key: "value"` in mix.exs.
# Usage: extract_mix_string <file> <key>
# Echoes the captured string (empty if not found).
extract_mix_string() {
    local file="$1"
    local key="$2"
    sed -n "s/.*${key}:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" "$file" | head -1
}
