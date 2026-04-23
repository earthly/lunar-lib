#!/bin/bash
set -e

# Collect Elixir/Hex dependencies from mix.exs (direct) and mix.lock (transitive resolved).

if [[ ! -f "mix.exs" ]]; then
    echo "No mix.exs found, exiting"
    exit 0
fi

# Direct deps: parse `{:name, "~> X.Y", ...}` tuples from mix.exs.
# Accepts both the short form `{:dep, "~> 1.0"}` and the keyword form
# `{:dep, version: "~> 1.0", ...}`, and keeps the first string literal
# after the atom as the version constraint.
direct_json=$(awk '
    /^[[:space:]]*\{:[a-z_][a-zA-Z0-9_]*[[:space:]]*,/ {
        # Extract dep atom after `:` up to next non-word char
        name=""
        for (i=1; i<=length($0); i++) {
            c=substr($0, i, 1)
            if (c==":") { start=i+1; break }
        }
        rest=substr($0, start)
        n=""
        for (i=1; i<=length(rest); i++) {
            c=substr(rest, i, 1)
            if (c ~ /[a-zA-Z0-9_]/) { n=n c } else { break }
        }
        name=n

        # Extract first "..." literal as version constraint
        version=""
        match($0, /"[^"]*"/)
        if (RSTART > 0) {
            version=substr($0, RSTART+1, RLENGTH-2)
        }

        if (name != "") {
            printf "{\"path\":\"%s\",\"version\":\"%s\"}\n", name, version
        }
    }
' mix.exs | jq -s '. // []')

# Transitive deps: mix.lock contains a map `%{"name" => {:hex, :name, "ver", ...}, ...}`.
# Parse each entry line-by-line using sed.
transitive_json="[]"
if [[ -f "mix.lock" ]]; then
    direct_names=$(jq '[.[].path]' <<<"$direct_json")
    transitive_json=$(sed -n 's/^[[:space:]]*"\([^"]*\)"[[:space:]]*:[[:space:]]*{:hex,[[:space:]]*:[a-zA-Z0-9_]*,[[:space:]]*"\([^"]*\)".*/{"path":"\1","version":"\2"}/p' mix.lock |
        jq -s --argjson direct_names "$direct_names" '
            [.[] | select(.path as $p | $direct_names | index($p) | not)]
        ')
fi

jq -n \
    --argjson direct "$direct_json" \
    --argjson transitive "$transitive_json" \
    '{
        direct: $direct,
        transitive: $transitive,
        source: {
            tool: "hex",
            integration: "code"
        }
    }' | lunar collect -j ".lang.elixir.dependencies" -
