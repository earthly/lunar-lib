#!/bin/bash
set -e

# Collect Rust dependencies from Cargo.toml and Cargo.lock

if [[ ! -f "Cargo.toml" ]]; then
    echo "No Cargo.toml found, exiting"
    exit 0
fi

# Parse dependencies from Cargo.toml sections using awk
# Extracts name and version requirement from [dependencies], [dev-dependencies], [build-dependencies]
parse_toml_deps() {
    local section="$1"
    awk -v section="$section" '
        BEGIN { in_section=0 }
        /^\[/ {
            if ($0 ~ "^\\[" section "\\]") { in_section=1; next }
            else if ($0 ~ "^\\[" section "\\.") { in_section=1; next }
            else { in_section=0 }
        }
        in_section && /^[a-zA-Z_-]/ {
            # Handle: name = "version" or name = { version = "..." }
            split($0, parts, "=")
            name = parts[1]
            gsub(/^[ \t]+|[ \t]+$/, "", name)
            rest = substr($0, index($0, "=") + 1)
            gsub(/^[ \t]+|[ \t]+$/, "", rest)

            version = ""
            features = "[]"
            if (rest ~ /^\{/) {
                # Table form: extract version and features
                if (match(rest, /version[ \t]*=[ \t]*"([^"]*)"/, m)) {
                    version = m[1]
                }
                if (match(rest, /features[ \t]*=[ \t]*\[([^\]]*)\]/, m)) {
                    # Parse features array
                    feat = m[1]
                    gsub(/"/, "", feat)
                    gsub(/[ \t]+/, "", feat)
                    n = split(feat, fa, ",")
                    features = "["
                    for (i=1; i<=n; i++) {
                        if (fa[i] != "") {
                            if (i > 1) features = features ","
                            features = features "\"" fa[i] "\""
                        }
                    }
                    features = features "]"
                }
            } else {
                # Simple form: name = "version"
                gsub(/"/, "", rest)
                version = rest
            }

            printf "{\"path\":\"%s\",\"version\":\"%s\",\"features\":%s}\n", name, version, features
        }
    ' Cargo.toml
}

# Parse each section
direct_json=$(parse_toml_deps "dependencies" | jq -s '. // []')
dev_json=$(parse_toml_deps "dev-dependencies" | jq -s '. // []')
build_json=$(parse_toml_deps "build-dependencies" | jq -s '. // []')

# Parse transitive deps from Cargo.lock if present
transitive_json="[]"
if [[ -f "Cargo.lock" ]]; then
    # Get direct dep names to exclude from transitive list
    direct_names=$(echo "$direct_json" "$dev_json" "$build_json" | jq -s 'add | map(.path) | unique')

    # Parse [[package]] entries from Cargo.lock
    transitive_json=$(awk '
        /^\[\[package\]\]/ { name=""; version=""; next }
        /^name = / { gsub(/"/, "", $3); name=$3 }
        /^version = / { gsub(/"/, "", $3); version=$3 }
        /^$/ || /^\[/ {
            if (name != "" && version != "") {
                printf "{\"path\":\"%s\",\"version\":\"%s\"}\n", name, version
            }
            name=""; version=""
        }
        END {
            if (name != "" && version != "") {
                printf "{\"path\":\"%s\",\"version\":\"%s\"}\n", name, version
            }
        }
    ' Cargo.lock | jq -s --argjson direct_names "$direct_names" '
        [.[] | select(.path as $p | $direct_names | index($p) | not)]
    ')
fi

# Build and collect
jq -n \
    --argjson direct "$direct_json" \
    --argjson dev "$dev_json" \
    --argjson build "$build_json" \
    --argjson transitive "$transitive_json" \
    '{
        direct: $direct,
        dev: $dev,
        build: $build,
        transitive: $transitive,
        source: {
            tool: "cargo",
            integration: "code"
        }
    }' | lunar collect -j ".lang.rust.dependencies" -
